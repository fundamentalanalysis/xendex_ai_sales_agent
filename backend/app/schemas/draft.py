"""Draft schemas for request/response validation."""
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field


# ============== Strategy Schemas ==============

class StrategyOutput(BaseModel):
    """Strategy engine output."""
    angle: str  # trigger-led, problem-hypothesis, case-study, quick-question
    pain_hypothesis: Optional[str] = None
    cta: str  # call, reply, resource, reply_yes_no
    tone: str = "professional"  # professional, casual, urgent
    personalization_depth: str = "medium"  # light, medium, deep


class EvidenceContext(BaseModel):
    """Evidence used for personalization."""
    triggers: Optional[List[dict]] = None
    linkedin_insights: Optional[dict] = None
    proof_points: Optional[List[dict]] = None
    pain_hypotheses: Optional[List[dict]] = None


# ============== Draft Schemas ==============

class DraftGenerateRequest(BaseModel):
    """Request to generate drafts."""
    lead_ids: List[UUID]
    campaign_id: Optional[UUID] = None
    template_id: Optional[UUID] = None
    touch_number: int = Field(1, ge=1, le=3)
    personalization_mode: Optional[str] = Field(None, pattern="^(light|medium|deep)$")
    regenerate_strategy: Optional[str] = None  # different_angle, softer_cta, more_casual


class DraftApproveRequest(BaseModel):
    """Request to approve a draft."""
    selected_subject: str
    approved_by: str
    scheduled_send_at: Optional[datetime] = None


class DraftRejectRequest(BaseModel):
    """Request to reject a draft."""
    rejection_reason: str


class DraftRegenerateRequest(BaseModel):
    """Request to regenerate a draft."""
    strategy_override: Optional[str] = None  # different_angle, softer_cta, more_casual, more_formal
    personalization_mode: Optional[str] = Field(None, pattern="^(light|medium|deep)$")


class BulkApproveRequest(BaseModel):
    """Request to bulk approve drafts."""
    draft_ids: List[UUID]
    approved_by: str
    scheduled_send_at: Optional[datetime] = None


class DraftUpdateRequest(BaseModel):
    """Request to update draft content."""
    subject: Optional[str] = Field(None, description="Custom subject line")
    body: Optional[str] = Field(None, description="Email body content (can include HTML)")


# ============== Response Schemas ==============

class DraftResponse(BaseModel):
    """Draft response."""
    id: UUID
    lead_id: UUID
    campaign_id: Optional[UUID] = None
    template_id: Optional[UUID] = None
    
    # Content
    touch_number: int
    subject_options: Optional[List[str]] = None
    selected_subject: Optional[str] = None
    body: str
    
    # Strategy
    strategy: Optional[StrategyOutput] = None
    evidence: Optional[EvidenceContext] = None
    personalization_mode: Optional[str] = None
    
    # Approval
    status: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    
    # Scheduling
    scheduled_send_at: Optional[datetime] = None
    
    created_at: datetime
    
    class Config:
        from_attributes = True


class DraftDetailResponse(DraftResponse):
    """Draft response with lead info."""
    lead_name: Optional[str] = None
    lead_company: Optional[str] = None
    lead_email: Optional[str] = None


class DraftListResponse(BaseModel):
    """Paginated draft list response."""
    items: List[DraftDetailResponse]
    total: int
    page: int
    page_size: int


class GenerateDraftsResult(BaseModel):
    """Result of draft generation."""
    generated: int
    failed: int
    draft_ids: List[UUID]
    errors: List[dict]
