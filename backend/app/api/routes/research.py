"""Research API endpoints."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.lead import Lead, LeadIntelligence
from app.schemas.research import (
    AnalyzeWebsiteRequest,
    YourCompanyProfile,
    TriggerResearchRequest,
    ResearchJobStatus,
)
from app.agents import (
    WebsiteAnalyzerAgent,
    LeadIntelligenceAgent,
    LinkedInAgent,
    GoogleResearchAgent,
    RiskFilterAgent,
)
from app.agents.intent_scorer import IntentScorer
from app.engine.normalizer import Normalizer
from app.config import settings

router = APIRouter()

# Cache for your company profile
_your_company_cache: Optional[dict] = None


@router.post("/analyze-website", response_model=dict)
async def analyze_website(
    request: AnalyzeWebsiteRequest,
):
    """
    Analyze your company website.
    
    This extracts:
    - Services/offerings
    - ICP constraints
    - Proof points
    - Positioning
    """
    global _your_company_cache
    
    # Return cached if available and not forcing refresh
    if _your_company_cache and not request.force_refresh:
        return _your_company_cache
    
    agent = WebsiteAnalyzerAgent()
    result = await agent.run(url=request.url)
    
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    
    # Cache the result
    _your_company_cache = result
    
    return result


@router.get("/your-profile", response_model=dict)
async def get_your_profile():
    """Get cached company profile."""
    global _your_company_cache
    
    if not _your_company_cache:
        # Try to analyze from settings
        if settings.your_website_url:
            agent = WebsiteAnalyzerAgent()
            _your_company_cache = await agent.run(url=settings.your_website_url)
        else:
            raise HTTPException(
                status_code=404, 
                detail="Company profile not available. Use /analyze-website first."
            )
    
    return _your_company_cache


@router.post("/lead/{lead_id}", response_model=dict)
async def run_lead_research(
    lead_id: UUID,
    request: TriggerResearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Run full research pipeline for a lead.
    
    This is a synchronous version for testing.
    For production, use the async /leads/{id}/research endpoint.
    """
    # Get lead
    stmt = select(Lead).where(Lead.id == lead_id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Get your company profile
    global _your_company_cache
    if not _your_company_cache:
        if settings.your_website_url:
            agent = WebsiteAnalyzerAgent()
            _your_company_cache = await agent.run(url=settings.your_website_url)
        else:
            _your_company_cache = {
                "services": [],
                "proof_points": [],
                "positioning": "We help companies succeed",
                "industries_served": [],
            }
    
    # Run agents
    results = {"agents_run": []}
    
    # 1. Lead Intelligence
    lead_intel_agent = LeadIntelligenceAgent()
    lead_intel = await lead_intel_agent.run(domain=lead.company_domain)
    results["lead_intelligence"] = lead_intel
    results["agents_run"].append("lead_intelligence")
    
    # 2. LinkedIn (if URL provided)
    linkedin_data = None
    if request.include_linkedin and lead.linkedin_url:
        linkedin_agent = LinkedInAgent()
        linkedin_data = await linkedin_agent.run(linkedin_url=lead.linkedin_url)
        results["linkedin"] = linkedin_data
        results["agents_run"].append("linkedin")
    
    # 3. Google Research (if enabled)
    triggers = []
    if request.include_google:
        google_agent = GoogleResearchAgent()
        google_result = await google_agent.run(
            company=lead.company_name,
            domain=lead.company_domain,
        )
        triggers = google_result.get("triggers", [])
        results["google_research"] = google_result
        results["agents_run"].append("google_research")
    
    # 4. Risk Filter
    risk_agent = RiskFilterAgent()
    risk_assessment = await risk_agent.run(
        lead_intelligence=lead_intel,
        google_triggers=triggers,
        linkedin_data=linkedin_data,
    )
    results["risk_assessment"] = risk_assessment
    results["agents_run"].append("risk_filter")
    
    # 5. Normalize and score
    normalizer = Normalizer()
    normalized = normalizer.normalize(
        your_company=_your_company_cache,
        lead_company=lead_intel,
        linkedin_data=linkedin_data,
        google_triggers=triggers,
        risk_assessment=risk_assessment,
    )
    results["normalized"] = normalized
    
    # 6. Save to database
    from datetime import datetime
    
    # Check if intelligence exists
    intel_stmt = select(LeadIntelligence).where(LeadIntelligence.lead_id == lead.id)
    intel_result = await db.execute(intel_stmt)
    intelligence = intel_result.scalar_one_or_none()
    
    if not intelligence:
        intelligence = LeadIntelligence(lead_id=lead.id)
        db.add(intelligence)
    
    # Update intelligence
    intelligence.your_services = _your_company_cache.get("services")
    intelligence.your_proof_points = _your_company_cache.get("proof_points")
    intelligence.your_positioning = _your_company_cache.get("positioning")
    
    intelligence.lead_offerings = lead_intel.get("offerings")
    intelligence.lead_pain_indicators = lead_intel.get("pain_indicators")
    intelligence.lead_buying_signals = lead_intel.get("buying_signals")
    intelligence.lead_tech_stack = lead_intel.get("tech_stack_hints")
    
    if linkedin_data:
        intelligence.linkedin_role = linkedin_data.get("role")
        intelligence.linkedin_seniority = linkedin_data.get("seniority")
        intelligence.linkedin_topics_30d = linkedin_data.get("topics_30d")
        intelligence.linkedin_job_change_days = linkedin_data.get("job_change_days")
        intelligence.linkedin_likely_initiatives = linkedin_data.get("likely_initiatives")
        intelligence.linkedin_raw_data = linkedin_data
    
    intelligence.triggers = triggers
    intelligence.pain_hypotheses = normalized.get("pain_hypotheses")
    intelligence.best_angle = normalized.get("recommended_angle")
    intelligence.researched_at = datetime.utcnow()
    intelligence.is_stale = False
    
    # Update lead scores
    scores = normalized.get("scores", {})
    lead.fit_score = scores.get("fit_score")
    lead.readiness_score = scores.get("readiness_score")
    lead.intent_score = scores.get("intent_score")
    lead.composite_score = scores.get("composite_score")
    lead.risk_level = risk_assessment.get("risk_level")
    lead.risk_reason = risk_assessment.get("reason")
    lead.status = "qualified" if risk_assessment.get("action") != "skip" else "disqualified"
    lead.researched_at = datetime.utcnow()
    
    await db.flush()
    
    results["scores"] = scores
    results["lead_status"] = lead.status
    
    return results


@router.get("/lead/{lead_id}/status", response_model=ResearchJobStatus)
async def get_research_status(
    lead_id: UUID,
    job_id: Optional[str] = None,
):
    """Check status of a research job."""
    # TODO: Integrate with Celery for real job status
    return ResearchJobStatus(
        job_id=job_id or "unknown",
        lead_id=lead_id,
        status="completed",
        progress=100,
    )
