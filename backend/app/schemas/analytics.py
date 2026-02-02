"""Analytics schemas for request/response validation."""
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


# ============== Overview Metrics ==============

class OverviewMetrics(BaseModel):
    """Dashboard overview metrics."""
    # Leads
    total_leads: int
    leads_researched: int
    leads_qualified: int
    leads_in_sequence: int
    leads_contacted: int
    leads_replied: int
    
    # Campaigns
    active_campaigns: int
    
    # Drafts
    pending_approvals: int
    
    # Performance (last 7 days)
    emails_sent_7d: int
    open_rate_7d: Optional[Decimal] = None
    reply_rate_7d: Optional[Decimal] = None
    bounce_rate_7d: Optional[Decimal] = None


# ============== Campaign Analytics ==============

class CampaignMetrics(BaseModel):
    """Metrics for a specific campaign."""
    campaign_id: UUID
    campaign_name: str
    
    # Volume
    total_leads: int
    emails_sent: int
    
    # Delivery
    delivered: int
    bounced: int
    delivery_rate: Optional[Decimal] = None
    
    # Engagement
    opened: int
    clicked: int
    replied: int
    open_rate: Optional[Decimal] = None
    reply_rate: Optional[Decimal] = None
    
    # Outcomes
    positive_replies: int
    negative_replies: int
    unsubscribed: int
    
    # By touch
    touch_1_sent: int = 0
    touch_2_sent: int = 0
    touch_3_sent: int = 0
    touch_1_reply_rate: Optional[Decimal] = None
    touch_2_reply_rate: Optional[Decimal] = None
    touch_3_reply_rate: Optional[Decimal] = None


# ============== Template Analytics ==============

class TemplateMetrics(BaseModel):
    """Metrics for a template."""
    template_id: UUID
    template_name: str
    type: str
    
    times_used: int
    open_rate: Optional[Decimal] = None
    reply_rate: Optional[Decimal] = None
    
    # By industry
    performance_by_industry: Optional[Dict[str, dict]] = None
    # By persona
    performance_by_persona: Optional[Dict[str, dict]] = None


class TemplateAnalyticsResponse(BaseModel):
    """All template metrics."""
    templates: List[TemplateMetrics]
    best_open_rate: Optional[TemplateMetrics] = None
    best_reply_rate: Optional[TemplateMetrics] = None


# ============== Funnel Analytics ==============

class FunnelStage(BaseModel):
    """A stage in the lead funnel."""
    stage: str
    count: int
    percentage: Optional[Decimal] = None


class FunnelResponse(BaseModel):
    """Lead funnel breakdown."""
    stages: List[FunnelStage]
    total_leads: int
    conversion_new_to_contacted: Optional[Decimal] = None
    conversion_contacted_to_replied: Optional[Decimal] = None
    conversion_replied_to_converted: Optional[Decimal] = None


# ============== Time Series ==============

class TimeSeriesPoint(BaseModel):
    """A point in time series data."""
    date: datetime
    value: int


class TimeSeriesResponse(BaseModel):
    """Time series data for charts."""
    metric: str
    data: List[TimeSeriesPoint]
    period: str  # daily, weekly, monthly
