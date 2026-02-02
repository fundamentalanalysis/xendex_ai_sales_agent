"""Template model for email templates."""
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.draft import Draft


class Template(Base, UUIDMixin, TimestampMixin):
    """Email template for consistent messaging."""
    
    __tablename__ = "templates"
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Type classification
    type: Mapped[str] = mapped_column(
        String(50), 
        nullable=False
    )  # trigger-led, problem-hypothesis, case-study, quick-question
    touch_number: Mapped[int] = mapped_column(Integer, default=1)  # T1, T2, T3
    
    # Content
    subject_template: Mapped[str] = mapped_column(Text, nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Personalization slots
    required_variables: Mapped[Optional[dict]] = mapped_column(JSONB)  # ["first_name", "trigger", "pain_hypothesis"]
    
    # Performance tracking
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    avg_open_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    avg_reply_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    drafts: Mapped[List["Draft"]] = relationship(back_populates="template")
