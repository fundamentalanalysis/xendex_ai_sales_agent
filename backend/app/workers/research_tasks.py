"""Research tasks for async execution."""
from uuid import UUID

from app.workers import celery_app


@celery_app.task(bind=True, name="research.run_pipeline")
def run_research_pipeline(self, lead_id: str):
    """
    Run full research pipeline for a lead.
    
    This is the async version that runs in Celery worker.
    """
    import asyncio
    import logging
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.config import settings
    from app.models.lead import Lead, LeadIntelligence
    from app.agents import (
        WebsiteAnalyzerAgent,
        LeadIntelligenceAgent,
        LinkedInAgent,
        GoogleResearchAgent,
        RiskFilterAgent,
    )
    from app.engine.normalizer import Normalizer
    
    # Configure basic logging to ensuring stdout output
    logging.basicConfig(level=logging.INFO)
    logger_std = logging.getLogger(__name__)
    
    print(f"DEBUG: Task run_research_pipeline received for lead_id={lead_id}")
    logger_std.info(f"DEBUG: Task started via standard logging for {lead_id}")

    async def _run():
        # Create async engine for this task
        engine = create_async_engine(settings.get_database_url)
        async_session = async_sessionmaker(engine, class_=AsyncSession)
        
        async with async_session() as db:
            # Get lead
            stmt = select(Lead).where(Lead.id == UUID(lead_id))
            result = await db.execute(stmt)
            lead = result.scalar_one_or_none()
            
            if not lead:
                print(f"DEBUG: Lead {lead_id} not found in database")
                return {"error": "Lead not found"}
            
            # Update status
            self.update_state(state="PROGRESS", meta={"step": "parallel_research"})
            
            import structlog
            logger = structlog.get_logger()
            print(f">>> STARTING RESEARCH FOR LEAD: {lead_id} ({lead.company_name})")
            logger.info("Starting research pipeline", lead_id=lead_id, company=lead.company_name)
            
            # Initialize agents
            print(">>> Initializing AI Agents...")
            lead_intel_agent = LeadIntelligenceAgent()
            linkedin_agent = LinkedInAgent()
            google_agent = GoogleResearchAgent()
            website_agent = WebsiteAnalyzerAgent()
            
            # Define async tasks for parallel execution
            async def run_lead_intel():
                print(f">>> Running Lead Intel for {lead.company_domain}...")
                return await lead_intel_agent.run(domain=lead.company_domain)
            
            async def run_linkedin():
                if lead.linkedin_url:
                    print(f">>> Running LinkedIn Research for {lead.linkedin_url}...")
                    return await linkedin_agent.run(
                        linkedin_url=lead.linkedin_url, 
                        bypass_cache=True,
                        lead_title=lead.persona,  # Fallback
                        lead_company=lead.company_name  # Fallback
                    )
                print(">>> Skipping LinkedIn (no URL provided)")
                return None
            
            async def run_google():
                print(f">>> Running Google Research for {lead.company_name}...")
                result = await google_agent.run(
                    company=lead.company_name,
                    domain=lead.company_domain,
                )
                return result.get("triggers", [])
            
            async def run_website():
                if settings.your_website_url:
                    print(f">>> Analyzing your website: {settings.your_website_url}...")
                    return await website_agent.run(url=settings.your_website_url)
                return {"services": [], "proof_points": [], "positioning": "", "industries_served": []}
            
            # Run independent agents in PARALLEL (major performance boost)
            print(">>> Launching parallel research tasks...")
            lead_intel, linkedin_data, triggers, your_company = await asyncio.gather(
                run_lead_intel(),
                run_linkedin(),
                run_google(),
                run_website(),
            )
            print(">>> Parallel research tasks completed.")
            
            # Risk Filter runs after (depends on other agents' results)
            self.update_state(state="PROGRESS", meta={"step": "risk_filter"})
            risk_agent = RiskFilterAgent()
            risk_assessment = await risk_agent.run(
                lead_intelligence=lead_intel,
                google_triggers=triggers,
                linkedin_data=linkedin_data,
            )
            
            # Transform linkedin_data to format expected by IntentScorer
            # IntentScorer expects: topics_30d, likely_initiatives, seniority, job_change_days
            transformed_linkedin = None
            if linkedin_data:
                activity = linkedin_data.get("personalization_signals", {})
                authority = linkedin_data.get("authority_signals", {})
                core_id = linkedin_data.get("core_identity", {})
                intent = linkedin_data.get("buying_intent_signals", {})
                
                transformed_linkedin = {
                    "role": core_id.get("current_title"),
                    "company": core_id.get("company"),
                    "seniority": authority.get("seniority_level"),
                    "job_change_days": None,  # Would need to calculate from experience
                    "topics_30d": activity.get("recent_topics", []),
                    "likely_initiatives": (
                        intent.get("growth_indicators", []) + 
                        intent.get("technology_mentions", [])
                    )[:5],
                    "conversation_starters": activity.get("conversation_starters", []),
                    # Pass through original data for other uses
                    **linkedin_data
                }
            
            # Normalize
            self.update_state(state="PROGRESS", meta={"step": "normalize"})
            normalizer = Normalizer()
            
            normalized = normalizer.normalize(
                your_company=your_company,
                lead_company=lead_intel,
                linkedin_data=transformed_linkedin,
                google_triggers=triggers,
                risk_assessment=risk_assessment,
            )
            
            # Save to database
            self.update_state(state="PROGRESS", meta={"step": "saving"})
            from datetime import datetime
            
            intel_stmt = select(LeadIntelligence).where(LeadIntelligence.lead_id == lead.id)
            intel_result = await db.execute(intel_stmt)
            intelligence = intel_result.scalar_one_or_none()
            
            if not intelligence:
                intelligence = LeadIntelligence(lead_id=lead.id)
                db.add(intelligence)
            
            # Update fields
            intelligence.lead_offerings = lead_intel.get("offerings")
            intelligence.lead_pain_indicators = lead_intel.get("pain_indicators")
            intelligence.lead_buying_signals = lead_intel.get("buying_signals")
            intelligence.triggers = triggers
            intelligence.pain_hypotheses = normalized.get("pain_hypotheses")
            intelligence.researched_at = datetime.utcnow()
            
            if linkedin_data:
                # DEBUG: Log the full LinkedIn data structure
                print(f">>> DEBUG: Full LinkedIn Data:")
                import json
                print(json.dumps(linkedin_data, indent=2, default=str))
                print(f">>> DEBUG: LinkedIn data keys: {list(linkedin_data.keys())}")
                print(f">>> DEBUG: LinkedIn data source: {linkedin_data.get('source')}")
                print(f">>> DEBUG: LinkedIn data success: {linkedin_data.get('success')}")
                
                # Extract from new agent structure
                core_id = linkedin_data.get("core_identity", {})
                authority = linkedin_data.get("authority_signals", {})
                activity = linkedin_data.get("activity_insights", {}) or linkedin_data.get("personalization_signals", {})
                lead_score = linkedin_data.get("lead_score", {})
                
                print(f">>> DEBUG: Seniority from authority: {authority.get('seniority_level')}")
                print(f">>> DEBUG: Decision maker: {authority.get('decision_maker')}")
                print(f">>> DEBUG: Budget authority: {authority.get('budget_authority')}")
                print(f">>> DEBUG: Lead score object: {lead_score}")
                print(f">>> DEBUG: Lead score .get('score'): {lead_score.get('score')}")
                
                # Map to database fields
                intelligence.linkedin_role = core_id.get("current_title") or linkedin_data.get("role")
                intelligence.linkedin_seniority = authority.get("seniority_level") or linkedin_data.get("seniority")
                intelligence.linkedin_topics_30d = (
                    activity.get("recent_topics") or 
                    activity.get("primary_topics") or 
                    linkedin_data.get("topics_30d")
                )
                
                # Store additional LinkedIn intelligence as JSON
                intelligence.linkedin_decision_power = authority.get("decision_maker")
                intelligence.linkedin_budget_authority = authority.get("budget_authority")
                
                # Handle lead_score - it might be a dict {"score": 15} or direct int
                if isinstance(lead_score, dict):
                    intelligence.linkedin_lead_score = lead_score.get("score")
                elif isinstance(lead_score, (int, float)):
                    intelligence.linkedin_lead_score = int(lead_score)
                else:
                    intelligence.linkedin_lead_score = None
                    
                intelligence.cold_email_hooks = linkedin_data.get("cold_email_hooks", [])
                intelligence.opening_line = linkedin_data.get("opening_line", {}).get("line") if isinstance(linkedin_data.get("opening_line"), dict) else linkedin_data.get("opening_line")
                
                print(f">>> DEBUG: Saved to DB - Seniority: {intelligence.linkedin_seniority}, Score: {intelligence.linkedin_lead_score}")
            
            # Update lead scores
            scores = normalized.get("scores", {})
            lead.fit_score = scores.get("fit_score")
            lead.readiness_score = scores.get("readiness_score")
            lead.intent_score = scores.get("intent_score")
            lead.composite_score = scores.get("composite_score")
            lead.risk_level = risk_assessment.get("risk_level")
            
            # Qualify lead based on composite score threshold
            composite = scores.get("composite_score", 0)
            if composite >= settings.qualification_threshold:
                lead.status = "not_started"
            else:
                lead.status = "not_qualified"
            
            lead.researched_at = datetime.utcnow()
            
            await db.commit()
            
            return {
                "lead_id": lead_id,
                "status": "completed",
                "scores": scores,
            }
    
    return asyncio.run(_run())


@celery_app.task(name="research.check_staleness")
def check_staleness():
    """Check all leads for stale data and mark for refresh."""
    import asyncio
    from datetime import datetime, timedelta
    from sqlalchemy import select, update
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.config import settings
    from app.models.lead import Lead, LeadIntelligence
    
    async def _run():
        engine = create_async_engine(settings.get_database_url)
        async_session = async_sessionmaker(engine, class_=AsyncSession)
        
        async with async_session() as db:
            threshold = datetime.utcnow() - timedelta(days=30)
            
            stmt = (
                update(LeadIntelligence)
                .where(LeadIntelligence.researched_at < threshold)
                .values(is_stale=True)
            )
            
            result = await db.execute(stmt)
            await db.commit()
            
            return {"marked_stale": result.rowcount}
    
    return asyncio.run(_run())
