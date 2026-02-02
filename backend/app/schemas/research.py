"""Research schemas for request/response validation."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


# ============== Website Analysis ==============

class AnalyzeWebsiteRequest(BaseModel):
    """Request to analyze your company website."""
    url: str = Field(..., description="Your company website URL")
    force_refresh: bool = False


class ServiceInfo(BaseModel):
    """A service/offering from your company."""
    name: str
    description: str
    icp_fit: Optional[str] = None  # Who this is best for


class ProofPoint(BaseModel):
    """A case study or proof point."""
    title: str
    outcome: str
    industry: Optional[str] = None
    metrics: Optional[List[str]] = None


class YourCompanyProfile(BaseModel):
    """Your company profile from website analysis."""
    services: List[ServiceInfo]
    proof_points: List[ProofPoint]
    positioning: str
    industries_served: List[str]
    analyzed_at: datetime


# ============== Lead Research ==============

class TriggerResearchRequest(BaseModel):
    """Request to run research for a lead."""
    lead_id: UUID
    include_linkedin: bool = True
    include_google: bool = True
    force_refresh: bool = False


class ResearchJobStatus(BaseModel):
    """Status of a research job."""
    job_id: str
    lead_id: UUID
    status: str  # pending, running, completed, failed
    progress: int = Field(ge=0, le=100)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


# ============== Google Research Queries ==============

class GoogleQuery(BaseModel):
    """A structured Google search query."""
    query: str
    category: str  # company_trigger, job_trigger, competitor_trigger
    expected_signal: str  # funding, acquisition, hiring, etc.


class GoogleResult(BaseModel):
    """A Google search result."""
    url: str
    title: str
    snippet: str
    source: Optional[str] = None
    date: Optional[str] = None


class GoogleResearchOutput(BaseModel):
    """Output from Google research agent."""
    queries_run: List[GoogleQuery]
    results: List[GoogleResult]
    triggers_found: List[dict]  # Matches Trigger schema
    researched_at: datetime


# ============== LinkedIn Research ==============

class LinkedInResearchOutput(BaseModel):
    """Output from LinkedIn research agent."""
    profile_url: Optional[str] = None
    role: Optional[str] = None
    seniority: Optional[str] = None
    company: Optional[str] = None
    headline: Optional[str] = None
    
    # Activity analysis
    topics_30d: List[str] = []
    post_count_30d: int = 0
    engagement_themes: List[str] = []
    
    # Signals
    job_change_days: Optional[int] = None
    likely_initiatives: List[str] = []
    
    # Raw data
    recent_posts: Optional[List[dict]] = None
    
    researched_at: datetime
    source: str = "manual"  # manual, phantombuster, scrape
