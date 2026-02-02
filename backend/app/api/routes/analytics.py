"""Analytics API endpoints."""
from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.lead import Lead
from app.models.in_sequence import Campaign, CampaignLead
from app.models.draft import Draft
from app.models.event import EmailEvent
from app.models.template import Template
from app.schemas.analytics import (
    OverviewMetrics,
    CampaignMetrics,
    TemplateAnalyticsResponse,
    TemplateMetrics,
    FunnelResponse,
    FunnelStage,
)

router = APIRouter()


@router.get("/overview", response_model=OverviewMetrics)
async def get_overview_metrics(
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard overview metrics."""
    
    # Lead counts by status - include ALL statuses
    lead_counts = {}
    for status in ["new", "researching", "qualified", "sequencing", "contacted", "replied", "converted", "completed", "disqualified", "inprogress"]:
        stmt = select(func.count(Lead.id)).where(Lead.status == status)
        result = await db.execute(stmt)
        lead_counts[status] = result.scalar() or 0
    
    total_leads = sum(lead_counts.values())
    
    # Active campaigns (campaigns with at least one active or ready lead)
    from sqlalchemy import or_
    active_campaigns_stmt = select(func.count(func.distinct(CampaignLead.campaign_id))).join(Campaign).where(
        CampaignLead.status.in_(["active", "ready"]),
        or_(
            Campaign.external_id.is_(None),
            ~Campaign.external_id.in_(["DEFAULT-FOLLOWUP", "MANUAL-FOLLOWUP"])
        )
    )
    active_campaigns_result = await db.execute(active_campaigns_stmt)
    active_campaigns = active_campaigns_result.scalar() or 0
    
    # Pending approvals
    pending_stmt = select(func.count(Draft.id)).where(Draft.status == "pending")
    pending_result = await db.execute(pending_stmt)
    pending_approvals = pending_result.scalar() or 0
    
    # 7-day email stats
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    
    sent_stmt = select(func.count(EmailEvent.id)).where(
        EmailEvent.event_type == "sent",
        EmailEvent.created_at >= seven_days_ago,
    )
    sent_result = await db.execute(sent_stmt)
    emails_sent_7d = sent_result.scalar() or 0
    
    # Lifetime replied count for the main counter
    replied_lifetime_stmt = select(func.count(EmailEvent.id)).where(EmailEvent.event_type == "replied")
    replied_lifetime_result = await db.execute(replied_lifetime_stmt)
    replied_lifetime = replied_lifetime_result.scalar() or 0
    
    # Calculate rates
    open_rate = None
    reply_rate = None
    bounce_rate = None
    
    if emails_sent_7d > 0:
        opened_stmt = select(func.count(EmailEvent.id)).where(
            EmailEvent.event_type == "opened",
            EmailEvent.created_at >= seven_days_ago,
        )
        opened_result = await db.execute(opened_stmt)
        opened = opened_result.scalar() or 0
        open_rate = Decimal(opened) / Decimal(emails_sent_7d)
        
        replied_7d_stmt = select(func.count(EmailEvent.id)).where(
            EmailEvent.event_type == "replied",
            EmailEvent.created_at >= seven_days_ago,
        )
        replied_7d_result = await db.execute(replied_7d_stmt)
        replied_7d = replied_7d_result.scalar() or 0
        reply_rate = Decimal(replied_7d) / Decimal(emails_sent_7d)
        
        bounced_stmt = select(func.count(EmailEvent.id)).where(
            EmailEvent.event_type == "bounced",
            EmailEvent.created_at >= seven_days_ago,
        )
        bounced_result = await db.execute(bounced_stmt)
        bounced = bounced_result.scalar() or 0
        bounce_rate = Decimal(bounced) / Decimal(emails_sent_7d)
    
    return OverviewMetrics(
        total_leads=total_leads,
        leads_researched=lead_counts.get("qualified", 0) + lead_counts.get("researching", 0) + lead_counts.get("sequencing", 0) + lead_counts.get("contacted", 0) + lead_counts.get("completed", 0),
        leads_qualified=lead_counts.get("qualified", 0) + lead_counts.get("researching", 0),
        leads_in_sequence=lead_counts.get("sequencing", 0) + lead_counts.get("contacted", 0),
        leads_contacted=lead_counts.get("contacted", 0) + lead_counts.get("sequencing", 0) + lead_counts.get("completed", 0) + lead_counts.get("replied", 0) + lead_counts.get("converted", 0),
        leads_replied=lead_counts.get("replied", 0) + lead_counts.get("converted", 0),
        active_campaigns=active_campaigns,
        pending_approvals=pending_approvals,
        emails_sent_7d=emails_sent_7d,
        open_rate_7d=open_rate,
        reply_rate_7d=reply_rate,
        bounce_rate_7d=bounce_rate,
    )


@router.get("/in-sequence/{campaign_id}", response_model=CampaignMetrics)
async def get_campaign_metrics(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get metrics for a specific campaign."""
    
    # Get campaign
    stmt = select(Campaign).where(Campaign.id == campaign_id)
    result = await db.execute(stmt)
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Count leads
    leads_stmt = select(func.count(CampaignLead.id)).where(CampaignLead.campaign_id == campaign_id)
    leads_result = await db.execute(leads_stmt)
    total_leads = leads_result.scalar() or 0
    
    # Event counts
    def count_events(event_type: str):
        stmt = select(func.count(EmailEvent.id)).where(
            EmailEvent.campaign_id == campaign_id,
            EmailEvent.event_type == event_type,
        )
        return stmt
    
    sent_result = await db.execute(count_events("sent"))
    sent = sent_result.scalar() or 0
    
    delivered_result = await db.execute(count_events("delivered"))
    delivered = delivered_result.scalar() or 0
    
    opened_result = await db.execute(count_events("opened"))
    opened = opened_result.scalar() or 0
    
    clicked_result = await db.execute(count_events("clicked"))
    clicked = clicked_result.scalar() or 0
    
    replied_result = await db.execute(count_events("replied"))
    replied = replied_result.scalar() or 0
    
    bounced_result = await db.execute(count_events("bounced"))
    bounced = bounced_result.scalar() or 0
    
    unsub_result = await db.execute(count_events("unsubscribed"))
    unsubscribed = unsub_result.scalar() or 0
    
    # Calculate rates
    delivery_rate = Decimal(delivered) / Decimal(sent) if sent > 0 else None
    open_rate = Decimal(opened) / Decimal(delivered) if delivered > 0 else None
    reply_rate = Decimal(replied) / Decimal(delivered) if delivered > 0 else None
    
    # Reply sentiment
    positive_stmt = select(func.count(EmailEvent.id)).where(
        EmailEvent.campaign_id == campaign_id,
        EmailEvent.event_type == "replied",
        EmailEvent.reply_sentiment == "positive",
    )
    positive_result = await db.execute(positive_stmt)
    positive_replies = positive_result.scalar() or 0
    
    negative_stmt = select(func.count(EmailEvent.id)).where(
        EmailEvent.campaign_id == campaign_id,
        EmailEvent.event_type == "replied",
        EmailEvent.reply_sentiment == "negative",
    )
    negative_result = await db.execute(negative_stmt)
    negative_replies = negative_result.scalar() or 0
    
    return CampaignMetrics(
        campaign_id=campaign_id,
        campaign_name=campaign.name,
        total_leads=total_leads,
        emails_sent=sent,
        delivered=delivered,
        bounced=bounced,
        delivery_rate=delivery_rate,
        opened=opened,
        clicked=clicked,
        replied=replied,
        open_rate=open_rate,
        reply_rate=reply_rate,
        positive_replies=positive_replies,
        negative_replies=negative_replies,
        unsubscribed=unsubscribed,
    )


@router.get("/templates", response_model=TemplateAnalyticsResponse)
async def get_template_analytics(
    db: AsyncSession = Depends(get_db),
):
    """Get performance analytics for all templates."""
    
    stmt = select(Template).where(Template.is_active == True)
    result = await db.execute(stmt)
    templates = result.scalars().all()
    
    template_metrics = []
    best_open = None
    best_reply = None
    
    for template in templates:
        metrics = TemplateMetrics(
            template_id=template.id,
            template_name=template.name,
            type=template.type,
            times_used=template.times_used,
            open_rate=template.avg_open_rate,
            reply_rate=template.avg_reply_rate,
        )
        template_metrics.append(metrics)
        
        if template.avg_open_rate:
            if not best_open or template.avg_open_rate > best_open.open_rate:
                best_open = metrics
        
        if template.avg_reply_rate:
            if not best_reply or template.avg_reply_rate > best_reply.reply_rate:
                best_reply = metrics
    
    return TemplateAnalyticsResponse(
        templates=template_metrics,
        best_open_rate=best_open,
        best_reply_rate=best_reply,
    )


@router.get("/funnel", response_model=FunnelResponse)
async def get_lead_funnel(
    db: AsyncSession = Depends(get_db),
):
    """Get lead funnel breakdown."""
    
    stages = ["new", "researching", "qualified", "sequencing", "contacted", "replied", "converted"]
    funnel_stages = []
    
    total = 0
    for status in stages:
        stmt = select(func.count(Lead.id)).where(Lead.status == status)
        result = await db.execute(stmt)
        count = result.scalar() or 0
        total += count
        funnel_stages.append(FunnelStage(stage=status, count=count))
    
    # Calculate percentages
    for stage in funnel_stages:
        if total > 0:
            stage.percentage = Decimal(stage.count) / Decimal(total)
    
    # Conversion rates
    contacted = next((s.count for s in funnel_stages if s.stage == "contacted"), 0)
    replied = next((s.count for s in funnel_stages if s.stage == "replied"), 0)
    converted = next((s.count for s in funnel_stages if s.stage == "converted"), 0)
    
    new_count = next((s.count for s in funnel_stages if s.stage == "new"), 0)
    
    return FunnelResponse(
        stages=funnel_stages,
        total_leads=total,
        conversion_new_to_contacted=Decimal(contacted) / Decimal(new_count) if new_count > 0 else None,
        conversion_contacted_to_replied=Decimal(replied) / Decimal(contacted) if contacted > 0 else None,
        conversion_replied_to_converted=Decimal(converted) / Decimal(replied) if replied > 0 else None,
    )
