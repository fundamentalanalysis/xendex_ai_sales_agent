"""In Sequence schemas for request/response validation."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============== Base Schemas ==============

class SequenceBase(BaseModel):
    """Base sequence fields."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    target_industry: Optional[str] = Field(None, max_length=100)
    target_persona: Optional[str] = Field(None, max_length=100)
    target_region: Optional[str] = Field(None, max_length=50)
    sequence_touches: int = Field(3, ge=1, le=10)
    touch_delays: List[int] = Field([3, 5], description="Days between touches")
    template_type: Optional[str] = Field(None, max_length=50)


class SequenceCreate(SequenceBase):
    """Schema for creating a sequence."""
    external_id: Optional[str] = Field(None, max_length=50)


class SequenceUpdate(BaseModel):
    """Schema for updating a sequence."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    target_industry: Optional[str] = Field(None, max_length=100)
    target_persona: Optional[str] = Field(None, max_length=100)
    target_region: Optional[str] = Field(None, max_length=50)
    sequence_touches: Optional[int] = Field(None, ge=1, le=10)
    touch_delays: Optional[List[int]] = None
    template_type: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = None


# ============== Sequence Lead Schemas ==============

class SequenceLeadStatus(BaseModel):
    """Status of a lead within a sequence."""
    lead_id: UUID
    current_touch: int
    next_touch_at: Optional[datetime] = None
    status: str
    stopped_reason: Optional[str] = None


class AddLeadsToSequence(BaseModel):
    """Request to add leads to a sequence."""
    lead_ids: List[UUID]


# ============== Response Schemas ==============

class SequenceResponse(BaseModel):
    """Sequence response."""
    id: UUID
    external_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    
    # Targeting
    target_industry: Optional[str] = None
    target_persona: Optional[str] = None
    target_region: Optional[str] = None
    
    # Sequence
    sequence_touches: int
    touch_delays: Optional[List[int]] = None
    template_type: Optional[str] = None
    
    # Status
    status: str
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    # Stats (Computed)
    total_leads: Optional[int] = 0
    active_leads: Optional[int] = 0
    completed_leads: Optional[int] = 0

    class Config:
        from_attributes = True


class SequenceDetailResponse(SequenceResponse):
    """Sequence response with stats."""
    total_leads: int = 0
    pending_leads: int = 0
    active_leads: int = 0
    completed_leads: int = 0
    stopped_leads: int = 0


class SequenceListResponse(BaseModel):
    """Paginated sequence list response."""
    items: List[SequenceResponse]
    total: int
    page: int
    page_size: int


# ============== Aliases for backward compatibility ==============
# These allow existing code to work during transition
CampaignCreate = SequenceCreate
CampaignUpdate = SequenceUpdate
CampaignResponse = SequenceResponse
CampaignDetailResponse = SequenceDetailResponse
CampaignListResponse = SequenceListResponse
CampaignLeadStatus = SequenceLeadStatus
AddLeadsToCampaign = AddLeadsToSequence
