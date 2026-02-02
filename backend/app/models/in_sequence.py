"""Campaign and CampaignLead models for In Sequence feature."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, Index, String, Text, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.draft import Draft
    from app.models.event import EmailEvent


class Campaign(Base, UUIDMixin, TimestampMixin):
    """Campaign/Sequence entity for organizing outreach sequences."""
    
    __tablename__ = "campaigns"
    
    # External ID
    external_id: Mapped[Optional[str]] = mapped_column(String(50), unique=True)  # "CAMP-ERP-01"
    
    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Targeting
    target_industry: Mapped[Optional[str]] = mapped_column(String(100))
    target_persona: Mapped[Optional[str]] = mapped_column(String(100))
    target_region: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Sequence config
    sequence_touches: Mapped[int] = mapped_column(Integer, default=3)
    touch_delays: Mapped[Optional[dict]] = mapped_column(JSONB, default=[3, 5])  # days between touches
    
    # Template association
    template_type: Mapped[Optional[str]] = mapped_column(String(50))  # trigger-led, problem-hypothesis, case-study
    
    # Status
    status: Mapped[str] = mapped_column(
        String(50), 
        default="draft"
    )  # draft, active, paused, completed
    
    # Relationships
    campaign_leads: Mapped[List["CampaignLead"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
    )
    drafts: Mapped[List["Draft"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
    )
    events: Mapped[List["EmailEvent"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
    )
    
    # Alias for "In Sequence" naming
    @property
    def sequence_leads(self):
        return self.campaign_leads


class CampaignLead(Base, UUIDMixin, TimestampMixin):
    """Association between Campaign/Sequence and Lead with sequence state."""
    
    __tablename__ = "campaign_leads"
    
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"),
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
    )
    
    # Sequence state
    current_touch: Mapped[int] = mapped_column(Integer, default=0)  # 0=not started, 1=T1 sent
    next_touch_at: Mapped[Optional[datetime]] = mapped_column()
    
    # Status
    status: Mapped[str] = mapped_column(
        String(50), 
        default="pending"
    )  # pending, active, paused, completed, stopped
    stopped_reason: Mapped[Optional[str]] = mapped_column(String(100))  # replied, bounced, unsubscribed, manual
    
    # Relationships
    campaign: Mapped["Campaign"] = relationship(back_populates="campaign_leads")
    lead: Mapped["Lead"] = relationship(back_populates="campaign_leads")
    
    # Alias for "In Sequence" naming
    @property
    def sequence(self):
        return self.campaign
    
    __table_args__ = (
        Index("idx_campaign_leads_unique", "campaign_id", "lead_id", unique=True),
        Index("idx_campaign_leads_next_touch", "next_touch_at"),
    )


# Aliases for "In Sequence" naming convention
Sequence = Campaign
SequenceLead = CampaignLead
