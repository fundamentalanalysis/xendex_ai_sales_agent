"""Lead and LeadIntelligence models."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, Index, Numeric, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.in_sequence import CampaignLead
    from app.models.draft import Draft
    from app.models.event import EmailEvent


class Lead(Base, UUIDMixin, TimestampMixin):
    """Lead entity - single source of truth for a sales prospect."""
    
    __tablename__ = "leads"
    
    # External ID
    external_id: Mapped[Optional[str]] = mapped_column(String(50), unique=True)
    
    # Basic info
    email: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500))
    mobile: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Classification
    region: Mapped[Optional[str]] = mapped_column(String(50))  # US, EU, APAC
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    persona: Mapped[Optional[str]] = mapped_column(String(100))  # IT Director, CFO
    
    # Scoring (computed)
    fit_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    readiness_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    intent_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    composite_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2))
    
    # Status
    status: Mapped[str] = mapped_column(
        String(50), 
        default="new"
    )  # new, researching, qualified, sequencing, contacted, replied, converted, disqualified
    risk_level: Mapped[Optional[str]] = mapped_column(String(20))  # low, medium, high
    risk_reason: Mapped[Optional[str]] = mapped_column(Text)
    
    # Settings
    personalization_mode: Mapped[str] = mapped_column(
        String(20), 
        default="medium"
    )  # light, medium, deep
    num_followups: Mapped[int] = mapped_column(default=3)
    followup_delay_days: Mapped[int] = mapped_column(default=3)
    
    # Timestamps
    researched_at: Mapped[Optional[datetime]] = mapped_column()
    last_contacted_at: Mapped[Optional[datetime]] = mapped_column()
    
    # Compliance
    unsubscribed_at: Mapped[Optional[datetime]] = mapped_column()
    consent_given_at: Mapped[Optional[datetime]] = mapped_column()
    data_retention_until: Mapped[Optional[datetime]] = mapped_column()
    
    # Relationships
    intelligence: Mapped[Optional["LeadIntelligence"]] = relationship(
        back_populates="lead",
        uselist=False,
        cascade="all, delete-orphan",
    )
    campaign_leads: Mapped[List["CampaignLead"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
    )
    drafts: Mapped[List["Draft"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
    )
    events: Mapped[List["EmailEvent"]] = relationship(
        back_populates="lead",
        cascade="all, delete-orphan",
    )
    
    __table_args__ = (
        Index("idx_leads_status", "status"),
        Index("idx_leads_composite_score", composite_score.desc()),
        Index("idx_leads_domain", "company_domain"),
    )
    
    @property
    def full_name(self) -> str:
        """Get full name."""
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p)


class LeadIntelligence(Base, UUIDMixin):
    """Research results for a lead."""
    
    __tablename__ = "lead_intelligence"
    
    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        unique=True,
    )
    
    # Your company analysis
    your_services: Mapped[Optional[dict]] = mapped_column(JSONB)  # [{name, description, icp_fit}]
    your_industries: Mapped[Optional[dict]] = mapped_column(JSONB) # ["Tech", "Finance"]
    your_proof_points: Mapped[Optional[dict]] = mapped_column(JSONB)  # [{case_study, outcome, industry}]
    your_positioning: Mapped[Optional[str]] = mapped_column(Text)
    
    # Lead company analysis
    lead_offerings: Mapped[Optional[dict]] = mapped_column(JSONB)
    lead_pain_indicators: Mapped[Optional[dict]] = mapped_column(JSONB)
    lead_buying_signals: Mapped[Optional[dict]] = mapped_column(JSONB)
    lead_tech_stack: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # LinkedIn data
    linkedin_role: Mapped[Optional[str]] = mapped_column(String(500))
    linkedin_seniority: Mapped[Optional[str]] = mapped_column(String(50))
    linkedin_topics_30d: Mapped[Optional[dict]] = mapped_column(JSONB)  # ["SAP modernization", "AI governance"]
    linkedin_job_change_days: Mapped[Optional[int]] = mapped_column()
    linkedin_likely_initiatives: Mapped[Optional[dict]] = mapped_column(JSONB)
    linkedin_raw_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Enhanced LinkedIn intelligence (new)
    linkedin_decision_power: Mapped[Optional[bool]] = mapped_column(Boolean)
    linkedin_budget_authority: Mapped[Optional[str]] = mapped_column(String(50))
    linkedin_lead_score: Mapped[Optional[int]] = mapped_column()
    cold_email_hooks: Mapped[Optional[dict]] = mapped_column(JSONB)  # ["Hook 1", "Hook 2"]
    opening_line: Mapped[Optional[str]] = mapped_column(Text)
    
    # Google triggers
    triggers: Mapped[Optional[dict]] = mapped_column(JSONB)  # [{type, recency_days, confidence, evidence_url}]
    
    # Computed insights
    pain_hypotheses: Mapped[Optional[dict]] = mapped_column(JSONB)  # [{hypothesis, confidence, evidence}]
    best_angle: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Metadata extracted from website (for scoring engine)
    company_size: Mapped[Optional[str]] = mapped_column(String(50))  # startup, small, medium, enterprise
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    gtm_motion: Mapped[Optional[str]] = mapped_column(String(50))    # enterprise, smb, self-serve, hybrid
    
    # Freshness
    researched_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationship
    lead: Mapped["Lead"] = relationship(back_populates="intelligence")
