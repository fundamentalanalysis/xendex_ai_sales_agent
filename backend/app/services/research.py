import asyncio
import logging
from datetime import datetime
from sqlalchemy import select
from app.dependencies import async_session_maker
from app.models.lead import Lead, LeadIntelligence
from app.agents import WebsiteAnalyzerAgent, LeadIntelligenceAgent, LinkedInAgent, GoogleResearchAgent, RiskFilterAgent
from app.engine.normalizer import Normalizer
from app.config import settings
import structlog

logger = structlog.get_logger()

async def run_research_background(str_lead_id: str):
    """Fallback single-loop research pipeline to bypass Celery & Redis connection limits."""
    logger.info("Starting background research without Celery", lead_id=str_lead_id)
    
    async with async_session_maker() as db:
        stmt = select(Lead).where(Lead.id == str_lead_id)
        result = await db.execute(stmt)
        lead = result.scalar_one_or_none()
        
        if not lead:
            logger.error("Lead not found in background task", lead_id=str_lead_id)
            return

        try:
            lead_intel_agent = LeadIntelligenceAgent()
            linkedin_agent = LinkedInAgent()
            google_agent = GoogleResearchAgent()
            website_agent = WebsiteAnalyzerAgent()
            
            logger.info("Running lead intel...", lead_id=str_lead_id)
            lead_intel = await lead_intel_agent.run(domain=lead.company_domain)
            
            logger.info("Running linkedin...", lead_id=str_lead_id)
            linkedin_data = await linkedin_agent.run(
                linkedin_url=lead.linkedin_url, bypass_cache=True, lead_title=lead.persona, lead_company=lead.company_name
            )
            
            logger.info("Running google research...", lead_id=str_lead_id)
            triggers_res = await google_agent.run(
                company=lead.company_name, domain=lead.company_domain,
            )
            triggers = triggers_res.get("triggers", [])
            
            logger.info("Running website analyzer for YOUR company context...", lead_id=str_lead_id)
            # Analyze YOUR company (from settings) to get context for fit comparison
            # Fallback to a target domain if not set, or a placeholder
            your_url = settings.your_website_url or "https://xendex.ai" 
            if not your_url.startswith("http"):
                your_url = f"https://{your_url}"
                
            your_company = await website_agent.run(url=your_url)
            if not your_company or not your_company.get("industries_served"):
                # Hardcoded fallback for known user company or trial
                logger.warning("Using hardcoded fallback for YOUR company industries", url=your_url)
                your_company = {
                    "services": ["AI Sales Automation", "Lead Intelligence"],
                    "proof_points": [],
                    "positioning": "Empowering sales teams with AI",
                    "industries_served": ["Technology", "Software", "SaaS", "AI", "Sales"]
                }

            
            logger.info("Running risk filter...", lead_id=str_lead_id)
            risk_agent = RiskFilterAgent()
            risk_assessment = await risk_agent.run(
                lead_intelligence=lead_intel, google_triggers=triggers, linkedin_data=linkedin_data,
            )
            
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
                    "job_change_days": None,
                    "topics_30d": activity.get("recent_topics", []),
                    "likely_initiatives": (intent.get("growth_indicators", []) + intent.get("technology_mentions", []))[:5],
                    "conversation_starters": activity.get("conversation_starters", []),
                    **linkedin_data
                }
            
            logger.info("Normalizing...", lead_id=str_lead_id)
            normalizer = Normalizer()
            normalized = normalizer.normalize(
                your_company=your_company, lead_company=lead_intel, linkedin_data=transformed_linkedin, google_triggers=triggers, risk_assessment=risk_assessment,
            )
            
            intel_stmt = select(LeadIntelligence).where(LeadIntelligence.lead_id == lead.id)
            intel_result = await db.execute(intel_stmt)
            intelligence = intel_result.scalars().first()
            if not intelligence:
                intelligence = LeadIntelligence(lead_id=lead.id)
                db.add(intelligence)
                
            intelligence.lead_offerings = lead_intel.get("offerings")
            intelligence.lead_pain_indicators = lead_intel.get("pain_indicators")
            intelligence.lead_buying_signals = lead_intel.get("buying_signals")
            intelligence.triggers = triggers
            intelligence.pain_hypotheses = normalized.get("pain_hypotheses")
            # Persist metadata for the scoring engine
            intelligence.your_industries = your_company.get("industries_served", [])
            intelligence.industry = lead_intel.get("industry")
            intelligence.company_size = lead_intel.get("company_size_estimate")
            intelligence.gtm_motion = lead_intel.get("gtm_motion")
            intelligence.best_angle = normalized.get("recommended_angle")
            
            # Using the MasterScoringEngine directly for accurate scoring!
            from app.engine.scoring_engine import MasterScoringEngine, SimpleDataExtractor
            
            try:
                fit_inputs = SimpleDataExtractor.extract_fit_inputs(lead, intelligence)
                readiness_inputs = SimpleDataExtractor.extract_readiness_inputs(lead, intelligence)
                intent_inputs = SimpleDataExtractor.extract_intent_inputs(lead, intelligence)
                
                engine = MasterScoringEngine(qualification_threshold=settings.qualification_threshold)
                combined_inputs = {
                    **fit_inputs, 
                    **readiness_inputs, 
                    **intent_inputs, 
                    "previous_status": lead.status
                }
                master_scores = engine.calculate_all_scores(**combined_inputs)
                
                lead.fit_score = master_scores.fit_score
                lead.readiness_score = master_scores.readiness_score
                lead.intent_score = master_scores.intent_score
                lead.composite_score = master_scores.composite_score
                lead.status = master_scores.qualification_status

                # Store Persisted Breakdown for display (to avoid automated recalculation)
                intelligence.fit_breakdown = {
                    "percentage": round(master_scores.fit_breakdown.percentage * 100, 1),
                    "components": master_scores.fit_breakdown.components,
                    "notes": master_scores.fit_breakdown.notes
                }
                intelligence.readiness_breakdown = {
                    "percentage": round(master_scores.readiness_breakdown.percentage * 100, 1),
                    "components": master_scores.readiness_breakdown.components,
                    "notes": master_scores.readiness_breakdown.notes
                }
            except Exception as score_exc:
                logger.error("Scoring engine failed during research, falling back...", exc_info=True)
                lead.status = "not_qualified"
                
            lead.risk_level = risk_assessment.get("risk_level")
            lead.researched_at = datetime.utcnow()
            await db.commit()
            logger.info("Background research complete.", lead_id=str_lead_id)
            
        except Exception as e:
            logger.error("Background research failed significantly", error=str(e), lead_id=str_lead_id)
            
            # FINAL HEURISTIC FALLBACK:
            # If research agents crashed (e.g. Playwright on Windows), 
            # try to scorebased ONLY on the CSV/provided leads data.
            try:
                from app.engine.scoring_engine import MasterScoringEngine, SimpleDataExtractor
                # pass None for intelligence since it failed/crashed
                fit_inputs = SimpleDataExtractor.extract_fit_inputs(lead, None)
                readiness_inputs = SimpleDataExtractor.extract_readiness_inputs(lead, None)
                intent_inputs = SimpleDataExtractor.extract_intent_inputs(lead, None)
                
                engine = MasterScoringEngine(qualification_threshold=settings.qualification_threshold)
                master_scores = engine.calculate_all_scores(
                    **{**fit_inputs, **readiness_inputs, **intent_inputs},
                    is_fallback=True
                )
                
                lead.fit_score = master_scores.fit_score
                lead.readiness_score = master_scores.readiness_score
                lead.intent_score = master_scores.intent_score
                lead.composite_score = master_scores.composite_score
                lead.status = master_scores.qualification_status
                logger.info("Heuristic fallback successful after research crash", lead_id=str_lead_id, score=float(lead.composite_score), is_fallback=True)
            except Exception as final_e:
                logger.error("All scoring fallbacks failed", error=str(final_e))
                lead.status = "research_error"
            
            await db.commit()

