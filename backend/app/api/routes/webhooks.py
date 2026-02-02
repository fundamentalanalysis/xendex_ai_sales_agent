"""Webhook endpoints for external integrations."""
import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.lead import Lead
from app.models.event import EmailEvent

logger = structlog.get_logger()
router = APIRouter()

@router.post("/resend")
async def resend_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Resend webhooks for email events (sent, opened, clicked, replied).
    
    Note: To receive replies via Resend, you must configure a Reply-To email
    and have a mechanism to forward those replies back to this webhook,
    or use Resend's Inbound Parse (if available).
    
    For now, we simulate/handle generic event structure.
    """
    payload = await request.json()
    logger.info("Received Resend webhook", payload=payload)
    
    event_type = payload.get("type")
    data = payload.get("data", {})
    email_id = data.get("email_id")
    
    if not event_type or not email_id:
        return {"status": "ignored"}
    
    # Try to find the event/draft by message ID
    stmt = select(EmailEvent).where(EmailEvent.sendgrid_message_id == email_id)
    result = await db.execute(stmt)
    existing_event = result.scalar_one_or_none()
    
    if not existing_event:
        logger.warning("Event not found for message_id", message_id=email_id)
        return {"status": "not_found"}
    
    # Create a new event for the activity (opening, clicking, replying)
    # Mapping Resend types to our EmailEvent types
    type_mapping = {
        "email.sent": "sent",
        "email.delivered": "delivered",
        "email.opened": "opened",
        "email.clicked": "clicked",
        "email.bounced": "bounced",
        "email.complained": "spam_complaint",
    }
    
    our_type = type_mapping.get(event_type)
    if not our_type:
        # Check if it's a simulated "reply" event
        if event_type == "email.replied":
            our_type = "replied"
        else:
            return {"status": "unsupported_type"}

    new_event = EmailEvent(
        lead_id=existing_event.lead_id,
        draft_id=existing_event.draft_id,
        campaign_id=existing_event.campaign_id,
        event_type=our_type,
        sendgrid_message_id=email_id,
        touch_number=existing_event.touch_number,
    )
    
    if our_type == "replied":
        new_event.body = data.get("content") or data.get("body")
        new_event.title = data.get("subject")
        
    db.add(new_event)
    await db.commit()
    
    logger.info("Processed email event", type=our_type, lead_id=str(existing_event.lead_id))
    
    return {"status": "success"}

@router.post("/test-reply")
async def test_reply(
    lead_id: str,
    content: str,
    subject: str = "Re: Follow up",
    db: AsyncSession = Depends(get_db),
):
    """Testing endpoint to simulate a reply for a lead."""
    from uuid import UUID
    
    # Find the last sent event for this lead
    stmt = (
        select(EmailEvent)
        .where(EmailEvent.lead_id == UUID(lead_id))
        .where(EmailEvent.event_type == "sent")
        .order_by(EmailEvent.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    last_sent = result.scalar_one_or_none()
    
    new_event = EmailEvent(
        lead_id=UUID(lead_id),
        draft_id=last_sent.draft_id if last_sent else None,
        campaign_id=last_sent.campaign_id if last_sent else None,
        event_type="replied",
        body=content,
        title=subject,
        touch_number=last_sent.touch_number if last_sent else 1,
    )
    
    db.add(new_event)
    
    # Update lead status to replied
    lead_stmt = select(Lead).where(Lead.id == UUID(lead_id))
    lead_result = await db.execute(lead_stmt)
    lead = lead_result.scalar_one_or_none()
    if lead:
        lead.status = "replied"
        
        # Stop Campaigns
        from app.models.in_sequence import CampaignLead
        camp_stmt = select(CampaignLead).where(CampaignLead.lead_id == UUID(lead_id))
        camp_leads_res = await db.execute(camp_stmt)
        camp_leads = camp_leads_res.scalars().all()
        for cl in camp_leads:
            if cl.status in ["active", "ready", "sequencing", "pending"]:
                cl.status = "stopped"
                cl.stopped_reason = "test_reply_simulated"
        
    await db.commit()
    
    return {"status": "success", "message": "Simulated reply added and lead status updated"}

@router.post("/manual-reply-log")
async def manual_reply_log(
    lead_id: str,
    content: str,
    subject: str = "Manual Logged Reply",
    db: AsyncSession = Depends(get_db),
):
    """Log a reply manually from the UI."""
    from uuid import UUID
    
    # Find the last sent event for context
    stmt = (
        select(EmailEvent)
        .where(EmailEvent.lead_id == UUID(lead_id))
        .where(EmailEvent.event_type == "sent")
        .order_by(EmailEvent.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    last_sent = result.scalar_one_or_none()
    
    new_event = EmailEvent(
        lead_id=UUID(lead_id),
        draft_id=last_sent.draft_id if last_sent else None,
        campaign_id=last_sent.campaign_id if last_sent else None,
        event_type="replied",
        body=content,
        title=subject,
        touch_number=last_sent.touch_number if last_sent else 1,
    )
    
    db.add(new_event)
    
    # Update lead status
    lead_stmt = select(Lead).where(Lead.id == UUID(lead_id))
    lead_result = await db.execute(lead_stmt)
    lead = lead_result.scalar_one_or_none()
    if lead:
        lead.status = "replied"
        
        # Stop Campaigns
        from app.models.in_sequence import CampaignLead
        camp_stmt = select(CampaignLead).where(CampaignLead.lead_id == UUID(lead_id))
        camp_leads_res = await db.execute(camp_stmt)
        camp_leads = camp_leads_res.scalars().all()
        for cl in camp_leads:
            if cl.status in ["active", "ready", "sequencing", "pending"]:
                cl.status = "stopped"
                cl.stopped_reason = "manual_reply_log"
        
    await db.commit()
    
    return {"status": "success", "message": "Reply logged manually"}
