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
    
    import structlog
    logger = structlog.get_logger()
    
    logger.info("Task run_research_pipeline received", lead_id=lead_id)

    async def _run():
        from app.dependencies import async_session_maker
        
        async with async_session_maker() as db:
            # Get lead
            stmt = select(Lead).where(Lead.id == UUID(lead_id))
            result = await db.execute(stmt)
            lead = result.scalar_one_or_none()
            
            if not lead:
                logger.error("Lead not found", lead_id=lead_id)
                return {"error": "Lead not found"}
            
            # Update status
            self.update_state(state="PROGRESS", meta={"step": "parallel_research"})
            
            logger.info("Starting research pipeline", lead_id=lead_id, company=lead.company_name)
            
            # Initialize agents
            logger.info("Initializing AI Agents")
            lead_intel_agent = LeadIntelligenceAgent()
            linkedin_agent = LinkedInAgent()
            google_agent = GoogleResearchAgent()
            website_agent = WebsiteAnalyzerAgent()
            
            # Define async tasks for parallel execution
            async def run_lead_intel():
                logger.debug("Running Lead Intel", domain=lead.company_domain)
                return await lead_intel_agent.run(domain=lead.company_domain)
            
            async def run_linkedin():
                if lead.linkedin_url:
                    logger.debug("Running LinkedIn Research", url=lead.linkedin_url)
                    return await linkedin_agent.run(
                        linkedin_url=lead.linkedin_url, 
                        bypass_cache=True,
                        lead_title=lead.persona,  # Fallback
                        lead_company=lead.company_name  # Fallback
                    )
                logger.debug("Skipping LinkedIn (no URL provided)")
                return None
            
            async def run_google():
                logger.debug("Running Google Research", company=lead.company_name)
                result = await google_agent.run(
                    company=lead.company_name,
                    domain=lead.company_domain,
                )
                return result.get("triggers", [])
            
            async def run_website():
                if settings.your_website_url:
                    logger.debug("Analyzing your website", url=settings.your_website_url)
                    return await website_agent.run(url=settings.your_website_url)
                return {"services": [], "proof_points": [], "positioning": "", "industries_served": []}
            
            # Run independent agents in PARALLEL with a hard timeout
            logger.info("Launching parallel research tasks (3 min timeout)")
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(
                        run_lead_intel(),
                        run_linkedin(),
                        run_google(),
                        run_website(),
                        return_exceptions=True
                    ),
                    timeout=180.0 # 3 minutes total
                )
            except asyncio.TimeoutError:
                logger.error("Research pipeline timed out after 3 minutes", lead_id=lead_id)
                # Fallback to empty results to allow the rest of the pipeline to fail gracefully
                results = [
                    Exception("Timeout"), 
                    Exception("Timeout"),
                    Exception("Timeout"),
                    {"services": [], "proof_points": [], "positioning": ""}
                ]
            
            # Unpack results with error handling
            def handle_result(res, name, default):
                if isinstance(res, Exception):
                    logger.error(f"Agent {name} failed", error=str(res))
                    return default
                return res if res is not None else default

            lead_intel = handle_result(results[0], "lead_intel", {"offerings": [], "pain_indicators": [], "buying_signals": []})
            linkedin_data = handle_result(results[1], "linkedin", None)
            triggers = handle_result(results[2], "google", [])
            your_company = handle_result(results[3], "website", {"services": [], "proof_points": [], "positioning": "", "industries_served": []})
            
            logger.info("Parallel research tasks completed (exceptions handled)")
            
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
            intelligence = intel_result.scalars().first()
            
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
                # Extract from new agent structure
                core_id = linkedin_data.get("core_identity", {})
                authority = linkedin_data.get("authority_signals", {})
                activity = linkedin_data.get("activity_insights", {}) or linkedin_data.get("personalization_signals", {})
                lead_score = linkedin_data.get("lead_score", {})
                
                # Map to database fields
                intelligence.linkedin_role = core_id.get("current_title") or linkedin_data.get("role")
                intelligence.linkedin_seniority = authority.get("seniority_level") or linkedin_data.get("seniority")
                intelligence.linkedin_topics_30d = (
                    activity.get("recent_topics") or 
                    activity.get("primary_topics") or 
                    linkedin_data.get("topics_30d")
                )
                
                # Store additional LinkedIn intelligence
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
                opening = linkedin_data.get("opening_line", {})
                intelligence.opening_line = opening.get("line") if isinstance(opening, dict) else opening
                
                logger.info("LinkedIn intel saved", seniority=intelligence.linkedin_seniority, score=intelligence.linkedin_lead_score)
            
            # Update lead scores — ONLY if research returned meaningful data
            scores = normalized.get("scores", {})
            composite = scores.get("composite_score", 0) or 0
            
            has_useful_data = (
                bool(lead_intel.get("offerings")) or
                bool(lead_intel.get("pain_indicators")) or
                bool(lead_intel.get("buying_signals")) or
                bool(triggers) or
                bool(linkedin_data)
            )
            
            if has_useful_data:
                # Save scores only when we have real data - never overwrite with zeros
                lead.fit_score = scores.get("fit_score")
                lead.readiness_score = scores.get("readiness_score")
                lead.intent_score = scores.get("intent_score")
                lead.composite_score = scores.get("composite_score")
                lead.risk_level = risk_assessment.get("risk_level")
                lead.researched_at = datetime.utcnow()
                
                # Qualify lead based on composite score threshold
                if composite >= settings.qualification_threshold:
                    lead.status = "qualified"
                    logger.info("Lead QUALIFIED", lead_id=lead_id, score=composite)
                else:
                    lead.status = "not_qualified"
                    logger.info("Lead NOT QUALIFIED", lead_id=lead_id, score=composite)
            else:
                # All agents returned empty data — mark as failed, don't overwrite scores
                logger.warning(
                    "Research returned no useful data — keeping existing scores",
                    lead_id=lead_id,
                    has_lead_intel=bool(lead_intel),
                    has_triggers=bool(triggers),
                    has_linkedin=bool(linkedin_data),
                )
                lead.status = "not_qualified"  # Not enough data to qualify
            
            await db.commit()
            
            return {
                "lead_id": lead_id,
                "status": "completed" if has_useful_data else "no_data",
                "scores": scores if has_useful_data else {},
                "has_useful_data": has_useful_data,
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


@celery_app.task(name="research.reset_stuck_leads")
def reset_stuck_leads():
    """Reset leads that have been in 'researching' status for too long (e.g., > 15 mins)."""
    import asyncio
    from datetime import datetime, timedelta
    from sqlalchemy import select, update
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.config import settings
    from app.models.lead import Lead
    
    async def _run():
        engine = create_async_engine(settings.get_database_url)
        async_session = async_sessionmaker(engine, class_=AsyncSession)
        
        async with async_session() as db:
            # Leads stuck in RESEARCHING for > 15 minutes
            threshold = datetime.utcnow() - timedelta(minutes=15)
            
            stmt = (
                update(Lead)
                .where(Lead.status == "researching")
                .where(Lead.updated_at < threshold)
                .values(status="not_qualified")
            )
            
            result = await db.execute(stmt)
            await db.commit()
            
            return {"reset_count": result.rowcount}
    
    return asyncio.run(_run())
