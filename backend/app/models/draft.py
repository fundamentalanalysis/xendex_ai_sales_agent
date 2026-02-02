"""Draft model for email drafts pending approval."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.in_sequence import Campaign
    from app.models.template import Template


class Draft(Base, UUIDMixin, TimestampMixin):
    """Email draft pending human approval."""
    
    __tablename__ = "drafts"
    
    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
    )
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"),
    )
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("templates.id", ondelete="SET NULL"),
    )
    
    # Content
    touch_number: Mapped[int] = mapped_column(Integer, default=1)
    subject_options: Mapped[Optional[dict]] = mapped_column(JSONB)  # ["Subject A", "Subject B", "Subject C"]
    selected_subject: Mapped[Optional[str]] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Strategy context
    strategy: Mapped[Optional[dict]] = mapped_column(JSONB)  # {angle, pain_hypothesis, cta, tone}
    evidence: Mapped[Optional[dict]] = mapped_column(JSONB)  # {triggers, linkedin_insights, proof_points}
    personalization_mode: Mapped[Optional[str]] = mapped_column(String(20))
    
    # Approval
    status: Mapped[str] = mapped_column(
        String(50), 
        default="pending"
    )  # pending, approved, rejected, regenerate
    approved_by: Mapped[Optional[str]] = mapped_column(String(255))
    approved_at: Mapped[Optional[datetime]] = mapped_column()
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)
    
    # Scheduling
    scheduled_send_at: Mapped[Optional[datetime]] = mapped_column()
    
    # Relationships
    lead: Mapped["Lead"] = relationship(back_populates="drafts")
    campaign: Mapped[Optional["Campaign"]] = relationship(back_populates="drafts")
    template: Mapped[Optional["Template"]] = relationship(back_populates="drafts")
    
    __table_args__ = (
        Index("idx_drafts_status", "status"),
        Index("idx_drafts_scheduled", "scheduled_send_at"),
    )
