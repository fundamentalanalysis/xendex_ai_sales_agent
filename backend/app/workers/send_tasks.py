"""Send tasks for email delivery."""
import asyncio
from uuid import UUID
from datetime import datetime
import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.workers import celery_app
from app.config import settings
from app.models.draft import Draft
from app.models.lead import Lead
from app.models.event import EmailEvent
from app.models.compliance import SuppressionList
from app.models.in_sequence import Campaign, CampaignLead
from app.integrations.sendgrid import EmailClient
from app.engine.draft_generator import DraftGenerator
from app.engine.strategy import StrategyEngine
from app.agents import WebsiteAnalyzerAgent

logger = structlog.get_logger()

@celery_app.task(name="worker.health_check")
def health_check():
    """Health check task to verify worker is alive."""
    print(f"\n[WORKER] >>> HEALTH CHECK at {datetime.utcnow()}")
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

@celery_app.task(
    bind=True, 
    name="send.send_email",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    retry_jitter=True
)
def send_email_task(self, draft_id: str):
    """Send an approved email via SendGrid."""
    print(f"\n[WORKER] >>> EXECUTING send_email_task for Draft ID: {draft_id}")
    
    async def _run():
        print(f"\n[DEBUG] >>> INITIATING EMAIL SEND for Draft: {draft_id}")
        logger.info("Starting email send task", draft_id=draft_id)

        engine = create_async_engine(
            settings.get_database_url,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        async_session = async_sessionmaker(engine, class_=AsyncSession)
        
        try:
            async with async_session() as db:
                # Get draft
                stmt = select(Draft).where(Draft.id == UUID(draft_id))
                result = await db.execute(stmt)
                draft = result.scalar_one_or_none()
                
                if not draft:
                    return {"error": "Draft not found"}
                
                if draft.status != "approved":
                    return {"error": "Draft not approved"}
                
                # Get lead
                lead_stmt = select(Lead).where(Lead.id == draft.lead_id)
                lead_result = await db.execute(lead_stmt)
                lead = lead_result.scalar_one_or_none()
                
                if not lead or not lead.email:
                    return {"error": "Lead email not available"}
                
                # Check suppression list
                suppression_stmt = select(SuppressionList).where(SuppressionList.email == lead.email)
                suppression_result = await db.execute(suppression_stmt)
                if suppression_result.scalar_one_or_none():
                    return {"error": "Email is on suppression list", "email": lead.email}
                
                # Send email
                email_client = EmailClient()
                send_result = await email_client.send_email(
                    to_email=lead.email,
                    to_name=f"{lead.first_name or ''} {lead.last_name or ''}".strip(),
                    subject=draft.selected_subject or draft.subject_options[0],
                    body=draft.body,
                    custom_args={
                        "draft_id": str(draft.id),
                        "lead_id": str(lead.id),
                        "campaign_id": str(draft.campaign_id) if draft.campaign_id else "",
                    },
                )
                
                if send_result.get("success"):
                    # Create sent event
                    event = EmailEvent(
                        draft_id=draft.id,
                        lead_id=lead.id,
                        campaign_id=draft.campaign_id,
                        event_type="sent",
                        touch_number=draft.touch_number,
                        sendgrid_message_id=send_result.get("message_id"),
                        title=draft.selected_subject or draft.subject_options[0],
                        body=draft.body,
                    )
                    db.add(event)
                    
                    cl = None
                    
                    # AUTO-ENROLL in Default Campaign if not in one
                    if not draft.campaign_id:
                        default_camp_stmt = select(Campaign).where(Campaign.external_id == "DEFAULT-FOLLOWUP")
                        default_camp_res = await db.execute(default_camp_stmt)
                        default_camp = default_camp_res.scalar_one_or_none()
                        
                        if default_camp:
                            print(f"[DEBUG] >>> Auto-enrolling {lead.company_name} in DEFAULT-FOLLOWUP campaign.")
                            draft.campaign_id = default_camp.id
                            
                            # Create/Get CampaignLead
                            cl_select = select(CampaignLead).where(
                                and_(CampaignLead.lead_id == lead.id, CampaignLead.campaign_id == default_camp.id)
                            )
                            cl_res = await db.execute(cl_select)
                            cl = cl_res.scalars().first()
                            
                            if not cl:
                                cl = CampaignLead(
                                    campaign_id=default_camp.id,
                                    lead_id=lead.id,
                                    status="active",
                                    current_touch=draft.touch_number or 1
                                )
                                db.add(cl)
                                await db.flush() # Ensure it exists for later updates
                            else:
                                cl.status = "active"
                                cl.current_touch = draft.touch_number or 1

                    if draft.campaign_id and cl is None:
                        cl_select = select(CampaignLead).where(
                            and_(CampaignLead.lead_id == lead.id, CampaignLead.campaign_id == draft.campaign_id)
                        )
                        cl_res = await db.execute(cl_select)
                        cl = cl_res.scalars().first()

                    # UPDATE CAMPAIGN LEAD STATE & ENROLLMENT
                    # Manual Sequence Flow:
                    # Touch 1 (from Drafts): Wait 1 min for reply, then show in InSequence
                    if draft.touch_number == 1:
                        lead.status = "inprogress" # Temporary hidden status
                        print(f"[DEBUG] >>> Touch 1 sent. Scheduling enrollment for {lead.company_name} in 60s.")
                        enroll_in_sequence_task.apply_async(
                            args=[str(lead.id), str(draft.campaign_id), str(draft.id)],
                            countdown=60
                        )
                    else:
                        # Touch 2+ (from InSequence): Just update status, NO auto-scheduling here
                        lead.status = "sequencing"
                        if cl:
                            cl.status = "active"
                            cl.current_touch = draft.touch_number
                            cl.last_contacted_at = datetime.utcnow()
                        
                        # Check if sequence is complete
                        if draft.campaign_id:
                            campaign_stmt = select(Campaign).where(Campaign.id == draft.campaign_id)
                            campaign_result = await db.execute(campaign_stmt)
                            campaign_obj = campaign_result.scalar_one_or_none()
                            touches_limit = campaign_obj.sequence_touches if campaign_obj else 3
                            
                            if draft.touch_number >= touches_limit:
                                lead.status = "completed"
                                if cl:
                                    cl.status = "completed"
                                print(f"[DEBUG] >>> SEQUENCE COMPLETE for {lead.company_name}")
                            else:
                                print(f"[DEBUG] >>> Touch {draft.touch_number} sent for {lead.company_name}. Waiting for manual trigger for next touch.")


                    # Save changes
                    await db.commit()
                    return {"success": True, "message_id": send_result.get("message_id")}
                else:
                    return {"success": False, "error": send_result.get("error")}
        finally:
            await engine.dispose()
    
    # Windows Proactor fix + Loop management
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    try:
        return loop.run_until_complete(_run())
    except Exception as exc:
        print(f"[WORKER] >>> Task failed: {exc}. Retrying...")
        raise self.retry(exc=exc)
    
@celery_app.task(
    bind=True,
    name="send.enroll_in_sequence",
    autoretry_for=(Exception,),
    max_retries=3
)
def enroll_in_sequence_task(self, lead_id: str, campaign_id: str, last_draft_id: str):
    """
    Called 1 minute after Touch 1. 
    Checks for reply, and if none, moves lead to 'contacted' (READY) status
    so it appears in the In Sequence queue.
    """
    print(f"\n[WORKER] >>> EXECUTING enroll_in_sequence_task for Lead: {lead_id}")
    
    async def _run():
        engine = create_async_engine(settings.get_database_url)
        async_session = async_sessionmaker(engine, class_=AsyncSession)
        async with async_session() as db:
            # Check for replies since last draft
            # Get draft to know when it was sent
            draft_stmt = select(Draft).where(Draft.id == UUID(last_draft_id))
            draft = (await db.execute(draft_stmt)).scalar_one_or_none()
            sent_at = draft.approved_at if draft else datetime.utcnow()
            
            reply_stmt = select(EmailEvent).where(
                and_(
                    EmailEvent.lead_id == UUID(lead_id),
                    EmailEvent.event_type == "replied",
                    EmailEvent.created_at >= sent_at
                )
            )
            reply = (await db.execute(reply_stmt)).scalar_one_or_none()
            
            if reply:
                print(f"[DEBUG] >>> Lead {lead_id} replied! Not enrolling in sequence.")
                # Lead status remains 'replied' (updated via webhook/check)
                return {"status": "replied_skipped"}
                
            # No reply, move to READY
            lead_stmt = select(Lead).where(Lead.id == UUID(lead_id))
            lead = (await db.execute(lead_stmt)).scalar_one_or_none()
            
            if lead:
                lead.status = "contacted"
                print(f"[DEBUG] >>> Lead {lead.company_name} status -> CONTACTED (READY)")
                
                # Ensure CampaignLead exists
                cl_stmt = select(CampaignLead).where(
                    and_(CampaignLead.lead_id == lead.id, CampaignLead.campaign_id == UUID(campaign_id))
                )
                cl = (await db.execute(cl_stmt)).scalars().first()
                if not cl:
                    cl = CampaignLead(
                        lead_id=lead.id,
                        campaign_id=UUID(campaign_id),
                        status="ready",
                        current_touch=1
                    )
                    db.add(cl)
                else:
                    cl.status = "ready"
                    cl.current_touch = 1
                
                await db.commit()
                return {"status": "enrolled_ready"}
        await engine.dispose()
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(_run())


@celery_app.task(
    bind=True,
    name="send.process_scheduled",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3
)
def process_scheduled_sends(self):
    """Process emails scheduled to send now."""
    async def _run():
        engine = create_async_engine(settings.get_database_url, pool_pre_ping=True)
        async_session = async_sessionmaker(engine, class_=AsyncSession)
        
        try:
            async with async_session() as db:
                now = datetime.utcnow()
                stmt = select(Draft).where(
                    Draft.status == "approved",
                    Draft.scheduled_send_at <= now,
                )
                result = await db.execute(stmt)
                drafts = result.scalars().all()
                
                queued = 0
                for draft in drafts:
                    send_email_task.delay(str(draft.id))
                    queued += 1
                return {"queued": queued}
        finally:
            await engine.dispose()
    
    # Windows loop fix
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(_run())
    except Exception as exc:
        raise self.retry(exc=exc)

@celery_app.task(
    bind=True, 
    name="send.follow_up",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3
)
def follow_up_task(self, lead_id: str, sent_at: str, touch_number: int, campaign_id: str):
    """Check for reply after sent_at, if no reply, send follow-up."""
    print(f"\n[WORKER] >>> EXECUTING follow_up_task. Lead={lead_id}, Touch={touch_number}, Camp={campaign_id}, CheckAfter={sent_at}")
    
    async def _run():
        sent_datetime = datetime.fromisoformat(sent_at)
        engine = create_async_engine(settings.get_database_url, pool_pre_ping=True)
        async_session = async_sessionmaker(engine, class_=AsyncSession)
        
        try:
            async with async_session() as db:
                # Check if replied
                reply_stmt = select(EmailEvent).where(
                    and_(
                        EmailEvent.lead_id == lead_id,
                        EmailEvent.event_type == "replied",
                        EmailEvent.created_at >= sent_datetime
                    )
                )
                reply_result = await db.execute(reply_stmt)
                if reply_result.scalar_one_or_none():
                    return {"skipped": "reply_received"}
                
                # Get campaign
                campaign_stmt = select(Campaign).where(Campaign.id == campaign_id)
                campaign_result = await db.execute(campaign_stmt)
                campaign_obj = campaign_result.scalar_one_or_none()
                if not campaign_obj or touch_number > campaign_obj.sequence_touches:
                    return {"skipped": "stop_sequence"}
                
                # No reply, create follow-up draft
                lead_stmt = select(Lead).where(Lead.id == lead_id).options(selectinload(Lead.intelligence))
                lead_result = await db.execute(lead_stmt)
                lead = lead_result.scalar_one_or_none()
                if not lead: return {"error": "Lead not found"}
                
                # Generate specialized follow-up content
                generator = DraftGenerator()
                strategy_engine = StrategyEngine()
                
                from app.api.routes.research import _your_company_cache
                your_company = _your_company_cache or {"services": [], "positioning": "We help companies succeed"}
                
                lead_data = {
                    "first_name": lead.first_name or "there",
                    "last_name": lead.last_name or "",
                    "company_name": lead.company_name,
                    "email": lead.email,
                    "persona": lead.persona,
                    "personalization_mode": lead.personalization_mode,
                }
                
                intel = lead.intelligence
                intelligence = {
                    "industry": intel.lead_offerings[0] if intel and intel.lead_offerings else "",
                    "pain_indicators": intel.lead_pain_indicators or [] if intel else [],
                    "buying_signals": intel.lead_buying_signals or [] if intel else [],
                    "triggers": intel.triggers or [] if intel else [],
                    "linkedin_data": {
                        "role": intel.linkedin_role if intel else None,
                        "seniority": intel.linkedin_seniority if intel else None,
                        "topics_30d": intel.linkedin_topics_30d or [] if intel else [],
                    }
                }
                
                strategy = strategy_engine.determine_strategy(
                    lead_intelligence=intelligence,
                    linkedin_data=intelligence.get("linkedin_data"),
                    triggers=intelligence.get("triggers"),
                    personalization_mode=lead_data["personalization_mode"],
                )
                
                draft_res = await generator.generate_draft(
                    lead_data=lead_data,
                    intelligence=intelligence,
                    your_company=your_company,
                    strategy=strategy,
                    touch_number=touch_number + 1,
                )
                
                new_draft = Draft(
                    lead_id=lead.id,
                    campaign_id=campaign_obj.id,
                    status="approved",
                    touch_number=touch_number + 1,
                    subject_options=draft_res.get("subject_options"),
                    selected_subject=draft_res.get("subject_options")[0] if draft_res.get("subject_options") else None,
                    body=draft_res.get("body", ""),
                    approved_at=datetime.utcnow()
                )
                db.add(new_draft)
                await db.commit()
                await db.refresh(new_draft)
                
                from app.workers.send_tasks import send_email_task
                send_email_task.delay(str(new_draft.id))
                return {"followup_sent": True}
        finally:
            await engine.dispose()
    
    # Windows loop fix
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    try:
        return loop.run_until_complete(_run())
    except Exception as exc:
        raise self.retry(exc=exc)

@celery_app.task(
    bind=True,
    name="send.run_orchestrator",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3
)
def run_orchestrator_task(self, campaign_id: str):
    """Run campaign orchestrator."""
    async def _run():
        print(f"\n[WORKER] >>> ORCHESTRATOR: Running for Campaign ID: {campaign_id}")
        engine = create_async_engine(settings.get_database_url, pool_pre_ping=True)
        async_session = async_sessionmaker(engine, class_=AsyncSession)
        
        try:
            async with async_session() as db:
                # 1. Get campaign
                stmt = select(Campaign).where(Campaign.id == UUID(campaign_id))
                result = await db.execute(stmt)
                campaign_obj = result.scalar_one_or_none()
                if not campaign_obj: return {"error": "Campaign not found"}
                
                # 2. Get leads
                cl_stmt = (
                    select(CampaignLead)
                    .where(CampaignLead.campaign_id == UUID(campaign_id))
                    .options(selectinload(CampaignLead.lead).selectinload(Lead.intelligence))
                )
                result = await db.execute(cl_stmt)
                campaign_leads = result.scalars().all()
                
                generator = DraftGenerator()
                strategy_engine = StrategyEngine()
                
                # Get company profile
                company_profile = None
                try:
                    from app.api.routes.research import _your_company_cache
                    company_profile = _your_company_cache
                except: pass
                
                if not company_profile:
                    if settings.your_website_url:
                        try:
                            agent = WebsiteAnalyzerAgent()
                            company_profile = await agent.run(url=settings.your_website_url)
                        except: pass
                
                if not company_profile:
                    company_profile = {"services": [], "positioning": "We help companies succeed."}
                
                processed = 0
                for cl in campaign_leads:
                    lead = cl.lead
                    if not lead or lead.status in ["replied", "converted", "disqualified"]:
                        continue
                    
                    # Check for existing draft 1
                    draft_stmt = select(Draft).where(
                        and_(Draft.lead_id == lead.id, Draft.campaign_id == campaign_obj.id, Draft.touch_number == 1)
                    )
                    if (await db.execute(draft_stmt)).scalars().first():
                        print(f"[WORKER] >>> Skipping {lead.company_name}: Draft exists")
                        continue
                    
                    if not lead.intelligence:
                        print(f"[WORKER] >>> Skipping {lead.company_name}: No intel")
                        continue
                        
                    try:
                        lead_data = {
                            "first_name": lead.first_name or "there",
                            "last_name": lead.last_name or "",
                            "company_name": lead.company_name,
                            "email": lead.email,
                            "persona": lead.persona,
                            "personalization_mode": lead.personalization_mode,
                        }
                        
                        intel = lead.intelligence
                        intelligence = {
                            "industry": intel.lead_offerings[0] if intel.lead_offerings else "",
                            "pain_indicators": intel.lead_pain_indicators or [],
                            "buying_signals": intel.lead_buying_signals or [],
                            "triggers": intel.triggers or [],
                            "linkedin_data": {
                                "role": intel.linkedin_role,
                                "seniority": intel.linkedin_seniority,
                                "topics_30d": intel.linkedin_topics_30d or [],
                                "likely_initiatives": intel.linkedin_likely_initiatives or [],
                            },
                        }
                        
                        strategy = strategy_engine.determine_strategy(
                            lead_intelligence=intelligence,
                            linkedin_data=intelligence.get("linkedin_data"),
                            triggers=intelligence.get("triggers"),
                            personalization_mode=lead_data["personalization_mode"],
                        )
                        
                        draft_res = await generator.generate_draft(
                            lead_data=lead_data,
                            intelligence=intelligence,
                            your_company=company_profile,
                            strategy=strategy,
                            touch_number=1,
                        )
                        
                        draft = Draft(
                            lead_id=lead.id,
                            campaign_id=campaign_obj.id,
                            touch_number=1,
                            subject_options=draft_res.get("subject_options"),
                            body=draft_res.get("body", ""),
                            strategy=strategy,
                            evidence=draft_res.get("evidence"),
                            personalization_mode=lead_data["personalization_mode"],
                            status="pending",
                        )
                        db.add(draft)
                        processed += 1
                        print(f"[WORKER] >>> Created draft for: {lead.company_name}")
                    except Exception as e:
                        print(f"[WORKER] >>> Error for {lead.id}: {e}")
                
                await db.commit()
                print(f"[WORKER] >>> Done. Processed {processed} leads.")
                return {"processed": processed}
        finally:
            await engine.dispose()
            
    # Windows loop fix
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    try:
        return loop.run_until_complete(_run())
    except Exception as exc:
        raise self.retry(exc=exc)
@celery_app.task(
    bind=True,
    name="send.check_replies",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3
)
def check_email_replies(self):
    """
    Poll 'Received' emails from Resend and sync to database.
    Updates lead status to 'replied' if a matching email is found.
    """
    logger.info("Polling for email replies...")
    
    async def _run():
        client = EmailClient()
        if not client.is_configured:
            logger.warning("Resend not configured, skipping reply check.")
            return
            
        result = await client.list_received_emails()
        if not result.get("success"):
            logger.error("Failed to fetch emails", error=result.get("error"))
            return
            
        emails = result.get("data", {}).get("data", [])
        
        engine = create_async_engine(settings.get_database_url, pool_pre_ping=True)
        async_session = async_sessionmaker(engine, class_=AsyncSession)
        
        async with async_session() as db:
            processed = 0
            for email in emails:
                # Parse sender
                from_email_raw = email.get("from", "")
                if "<" in from_email_raw:
                    sender_email = from_email_raw.split("<")[1].strip(">").strip()
                else:
                    sender_email = from_email_raw.strip()
                
                re_id = email.get("id")
                subject = email.get("subject", "No Subject")
                
                # Check duplication
                event_stmt = select(EmailEvent).where(EmailEvent.sendgrid_message_id == re_id)
                if (await db.execute(event_stmt)).scalar_one_or_none():
                    continue
                
                # Find Lead
                stmt = select(Lead).where(Lead.email == sender_email)
                lead = (await db.execute(stmt)).scalars().first()
                
                if lead:
                    # Create Event
                    # Get content lazily or use subject as fallback
                    content = "View in email history"
                    try:
                         # Optional: Fetch body if needed, but might be slow for loop
                         pass 
                    except: pass
                    
                    created_at = datetime.utcnow()
                    if email.get("created_at"):
                        ts_str = email.get("created_at").replace('Z', '+00:00')
                        if ' ' in ts_str and 'T' not in ts_str: ts_str = ts_str.replace(' ', 'T')
                        try:
                            created_at = datetime.fromisoformat(ts_str)
                        except: pass
                    
                    new_event = EmailEvent(
                        lead_id=lead.id,
                        event_type="replied",
                        title=subject,
                        body=content,
                        sendgrid_message_id=re_id,
                        created_at=created_at
                    )
                    db.add(new_event)
                    
                    # Update Status
                    if lead.status not in ["replied", "converted"]:
                        lead.status = "replied"
                        
                        # Stop Campaigns
                        camp_stmt = select(CampaignLead).where(CampaignLead.lead_id == lead.id)
                        camp_leads = (await db.execute(camp_stmt)).scalars().all()
                        for cl in camp_leads:
                            if cl.status in ["active", "ready", "sequencing", "pending"]:
                                cl.status = "stopped"
                                cl.stopped_reason = "replied"
                    
                    processed += 1
            
            await db.commit()
            return {"processed": processed}
        await engine.dispose()

    # Windows loop fix
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    try:
        return loop.run_until_complete(_run())
    except Exception as exc:
        raise self.retry(exc=exc)
