"""Compliance models: SuppressionList, AuditLog, DomainHealth."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Index, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class SuppressionList(Base, UUIDMixin):
    """Email suppression list for compliance."""
    
    __tablename__ = "suppression_list"
    
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String(255))
    reason: Mapped[Optional[str]] = mapped_column(String(50))  # unsubscribed, bounced, spam_complaint, manual
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    
    __table_args__ = (
        Index("idx_suppression_email", "email"),
        Index("idx_suppression_domain", "domain"),
    )


class AuditLog(Base, UUIDMixin):
    """Audit trail for compliance."""
    
    __tablename__ = "audit_log"
    
    entity_type: Mapped[Optional[str]] = mapped_column(String(50))  # lead, draft, campaign
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    action: Mapped[Optional[str]] = mapped_column(String(50))  # created, updated, approved, sent
    actor: Mapped[Optional[str]] = mapped_column(String(255))
    details: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class DomainHealth(Base, UUIDMixin):
    """Domain health tracking for deliverability."""
    
    __tablename__ = "domain_health"
    
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    
    # Warmup
    warmup_started_at: Mapped[Optional[datetime]] = mapped_column()
    warmup_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    daily_limit: Mapped[int] = mapped_column(Integer, default=50)
    
    # Health metrics
    bounce_rate_7d: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    spam_rate_7d: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    
    # DNS config
    spf_valid: Mapped[Optional[bool]] = mapped_column(Boolean)
    dkim_valid: Mapped[Optional[bool]] = mapped_column(Boolean)
    dmarc_valid: Mapped[Optional[bool]] = mapped_column(Boolean)
    last_dns_check_at: Mapped[Optional[datetime]] = mapped_column()
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
