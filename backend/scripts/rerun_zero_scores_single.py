import asyncio
import os
import sys

sys.path.append(os.getcwd())

from app.dependencies import engine
from sqlalchemy import select
from app.models.lead import Lead, LeadIntelligence
from app.workers.research_tasks import run_research_pipeline

# Instead of using celery task logic (which creates loops), we duplicate the inner logic but use ONE loop!
async def run_single_loop():
    from app.dependencies import async_session_maker
    from app.models.lead import Lead, LeadIntelligence
    from app.agents import WebsiteAnalyzerAgent, LeadIntelligenceAgent, LinkedInAgent, GoogleResearchAgent, RiskFilterAgent
    from app.engine.normalizer import Normalizer
    from datetime import datetime
    
    leads = [
        "9fccb0b1-ee14-490c-9223-83e61819e4c2",
        "c8030257-8c2c-4144-aba4-91adc3c53ebd"
    ]
    
    async with async_session_maker() as db:
        for lead_id in leads:
            stmt = select(Lead).where(Lead.id == lead_id)
            result = await db.execute(stmt)
            lead = result.scalar_one_or_none()
            
            if not lead:
                continue
                
            print(f"Starting research pipeline for {lead.company_name} (ID: {lead_id})")
            
            lead_intel_agent = LeadIntelligenceAgent()
            linkedin_agent = LinkedInAgent()
            google_agent = GoogleResearchAgent()
            website_agent = WebsiteAnalyzerAgent()
            
            print(f"Running parallel research tasks ...")
            try:
                # To prevent blocking each other, we run sequentially here for debugging
                print("Running lead intel...")
                lead_intel = await lead_intel_agent.run(domain=lead.company_domain)
                
                print("Running linkedin...")
                linkedin_data = await linkedin_agent.run(
                    linkedin_url=lead.linkedin_url, bypass_cache=True, lead_title=lead.persona, lead_company=lead.company_name
                )
                
                print("Running google research...")
                triggers_res = await google_agent.run(
                    company=lead.company_name, domain=lead.company_domain,
                )
                triggers = triggers_res.get("triggers", [])
                
                print("Running website analyzer...")
                from app.config import settings
                if settings.your_website_url:
                    your_company = await website_agent.run(url=settings.your_website_url)
                else:
                    your_company = {"services": [], "proof_points": [], "positioning": "", "industries_served": []}
                
            except Exception as e:
                print(f"Error during parallel step: {e}")
                
            print("Running risk filter...")
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
            
            print("Normalizing...")
            normalizer = Normalizer()
            normalized = normalizer.normalize(
                your_company=your_company, lead_company=lead_intel, linkedin_data=transformed_linkedin, google_triggers=triggers, risk_assessment=risk_assessment,
            )
            
            intel_stmt = select(LeadIntelligence).where(LeadIntelligence.lead_id == lead.id)
            intel_result = await db.execute(intel_stmt)
            intelligence = intel_result.scalar_one_or_none()
            if not intelligence:
                intelligence = LeadIntelligence(lead_id=lead.id)
                db.add(intelligence)
                
            intelligence.lead_offerings = lead_intel.get("offerings")
            intelligence.lead_pain_indicators = lead_intel.get("pain_indicators")
            intelligence.lead_buying_signals = lead_intel.get("buying_signals")
            intelligence.triggers = triggers
            intelligence.pain_hypotheses = normalized.get("pain_hypotheses")
            intelligence.researched_at = datetime.utcnow()
            
            scores = normalized.get("scores", {})
            print(f"SCORES: {scores}")
            has_useful_data = bool(lead_intel.get("offerings")) or bool(lead_intel.get("pain_indicators")) or bool(lead_intel.get("buying_signals")) or bool(triggers) or bool(linkedin_data)
            
            if has_useful_data:
                lead.fit_score = scores.get("fit_score")
                lead.readiness_score = scores.get("readiness_score")
                lead.intent_score = scores.get("intent_score")
                lead.composite_score = scores.get("composite_score")
                lead.risk_level = risk_assessment.get("risk_level")
                lead.researched_at = datetime.utcnow()
                
                if (scores.get("composite_score", 0) or 0) >= settings.qualification_threshold:
                    lead.status = "qualified"
                else:
                    lead.status = "not_qualified"
            else:
                lead.status = "not_qualified"
                
            await db.commit()
            print(f"Done storing for {lead.company_name}\n")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_single_loop())

