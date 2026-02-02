"""Lead schemas for request/response validation."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, HttpUrl


# ============== Base Schemas ==============

class LeadBase(BaseModel):
    """Base lead fields."""
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    company_name: str = Field(..., max_length=255)
    company_domain: str = Field(..., max_length=255)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    mobile: Optional[str] = Field(None, max_length=50)
    region: Optional[str] = Field(None, max_length=50)
    industry: Optional[str] = Field(None, max_length=100)
    persona: Optional[str] = Field(None, max_length=100)
    personalization_mode: str = Field("medium", pattern="^(light|medium|deep)$")
    num_followups: int = Field(3, ge=1, le=10)
    followup_delay_days: int = Field(3, ge=1, le=30)


class LeadCreate(LeadBase):
    """Schema for creating a lead."""
    external_id: Optional[str] = Field(None, max_length=50)


class LeadUpdate(BaseModel):
    """Schema for updating a lead."""
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    company_name: Optional[str] = Field(None, max_length=255)
    company_domain: Optional[str] = Field(None, max_length=255)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    mobile: Optional[str] = Field(None, max_length=50)
    region: Optional[str] = Field(None, max_length=50)
    industry: Optional[str] = Field(None, max_length=100)
    persona: Optional[str] = Field(None, max_length=100)
    personalization_mode: Optional[str] = Field(None, pattern="^(light|medium|deep)$")
    status: Optional[str] = None
    num_followups: Optional[int] = Field(None, ge=1, le=10)
    followup_delay_days: Optional[int] = Field(None, ge=1, le=30)


# ============== Intelligence Schemas ==============

class LinkedInData(BaseModel):
    """LinkedIn intelligence data."""
    role: Optional[str] = None
    seniority: Optional[str] = None
    topics_30d: Optional[List[str]] = None
    job_change_days: Optional[int] = None
    likely_initiatives: Optional[List[str]] = None


class Trigger(BaseModel):
    """A research trigger from Google."""
    type: str  # funding, acquisition, hiring, new_exec
    recency_days: Optional[int] = None
    confidence: float = Field(ge=0, le=1)
    evidence_url: Optional[str] = None
    summary: Optional[str] = None


class PainHypothesis(BaseModel):
    """A pain hypothesis for the lead."""
    hypothesis: str
    confidence: float = Field(ge=0, le=1)
    evidence: Optional[str] = None


class LeadIntelligenceResponse(BaseModel):
    """Lead intelligence response."""
    id: UUID
    lead_id: UUID
    
    # Your company
    your_services: Optional[List[dict]] = None
    your_proof_points: Optional[List[dict]] = None
    your_positioning: Optional[str] = None
    
    # Lead company
    lead_offerings: Optional[List[dict]] = None
    lead_pain_indicators: Optional[List[str]] = None
    lead_buying_signals: Optional[List[str]] = None
    lead_tech_stack: Optional[List[str]] = None
    
    # LinkedIn
    linkedin_role: Optional[str] = None
    linkedin_seniority: Optional[str] = None
    linkedin_topics_30d: Optional[List[str]] = None
    linkedin_job_change_days: Optional[int] = None
    linkedin_likely_initiatives: Optional[List[str]] = None
    
    # Triggers
    triggers: Optional[List[Trigger]] = None
    
    # Insights
    pain_hypotheses: Optional[List[PainHypothesis]] = None
    best_angle: Optional[str] = None
    
    # Freshness
    researched_at: Optional[datetime] = None
    is_stale: bool = False
    
    class Config:
        from_attributes = True


# ============== Response Schemas ==============

class LeadResponse(BaseModel):
    """Lead response with all fields."""
    id: UUID
    external_id: Optional[str] = None
    
    # Basic info
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: str
    company_domain: str
    linkedin_url: Optional[str] = None
    mobile: Optional[str] = None
    
    # Classification
    region: Optional[str] = None
    industry: Optional[str] = None
    persona: Optional[str] = None
    
    # Scoring
    fit_score: Optional[Decimal] = None
    readiness_score: Optional[Decimal] = None
    intent_score: Optional[Decimal] = None
    composite_score: Optional[Decimal] = None
    
    # Status
    status: str
    risk_level: Optional[str] = None
    risk_reason: Optional[str] = None
    personalization_mode: str
    num_followups: int
    followup_delay_days: int
    
    # Engagement
    has_replied: bool = False
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    researched_at: Optional[datetime] = None
    last_contacted_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class EmailEventResponse(BaseModel):
    """Email event response."""
    id: UUID
    event_type: str
    touch_number: Optional[int] = None
    created_at: datetime
    title: Optional[str] = None
    body: Optional[str] = None
    reply_sentiment: Optional[str] = None
    reply_intent: Optional[str] = None
    
    class Config:
        from_attributes = True


class LeadDetailResponse(LeadResponse):
    """Lead response with intelligence and events included."""
    intelligence: Optional[LeadIntelligenceResponse] = None
    events: List[EmailEventResponse] = []


class LeadListResponse(BaseModel):
    """Paginated lead list response."""
    items: List[LeadResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ============== Bulk Import ==============

class BulkLeadImport(BaseModel):
    """Bulk import request."""
    leads: List[LeadCreate]


class BulkImportResult(BaseModel):
    """Bulk import result."""
    created: int
    skipped: int
    errors: List[dict]
