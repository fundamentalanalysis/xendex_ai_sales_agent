"""EmailEvent model for tracking email delivery and engagement."""
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.in_sequence import Campaign
    from app.models.draft import Draft


class EmailEvent(Base, UUIDMixin, TimestampMixin):
    """Email delivery and engagement event."""
    
    __tablename__ = "email_events"
    
    draft_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("drafts.id", ondelete="SET NULL"),
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
    )
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("campaigns.id", ondelete="SET NULL"),
    )
    
    # Event details
    event_type: Mapped[str] = mapped_column(
        String(50), 
        nullable=False
    )  # sent, delivered, opened, clicked, replied, bounced, unsubscribed, spam_complaint
    touch_number: Mapped[Optional[int]] = mapped_column(Integer)
    
    # SendGrid metadata
    sendgrid_message_id: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Content (for replies)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    body: Mapped[Optional[str]] = mapped_column(String)  # The actual text of the reply
    
    # Reply analysis (if applicable)
    reply_sentiment: Mapped[Optional[str]] = mapped_column(String(20))  # positive, neutral, negative
    reply_intent: Mapped[Optional[str]] = mapped_column(String(50))  # interested, not_now, not_interested, out_of_office
    
    # Relationships
    lead: Mapped["Lead"] = relationship(back_populates="events")
    campaign: Mapped[Optional["Campaign"]] = relationship(back_populates="events")
    draft: Mapped[Optional["Draft"]] = relationship()
    
    __table_args__ = (
        Index("idx_events_lead", "lead_id"),
        Index("idx_events_type", "event_type"),
        Index("idx_events_campaign", "campaign_id"),
    )
