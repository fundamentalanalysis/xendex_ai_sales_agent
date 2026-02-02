"""API routes for email operations."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.integrations.sendgrid import EmailClient
from app.schemas.email import ReceivedEmailList, ReceivedEmailDetail

router = APIRouter(prefix="/emails", tags=["emails"])


@router.get("/received", response_model=ReceivedEmailList)
async def list_received_emails(
    db: AsyncSession = Depends(get_db),
) -> ReceivedEmailList:
    """List all received emails."""
    client = EmailClient()
    result = await client.list_received_emails()
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return ReceivedEmailList(**result["data"])


@router.get("/received/{email_id}", response_model=ReceivedEmailDetail)
async def get_received_email(
    email_id: str,
    db: AsyncSession = Depends(get_db),
) -> ReceivedEmailDetail:
    """Get details of a specific received email."""
    client = EmailClient()
    result = await client.get_received_email(email_id)
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])
    
    # Debug logging to inspect structure
    print(f"\n[DEBUG] >>> RAW RESEND RESPONSE KEYS: {result['data'].keys()}")
    if 'html' in result['data']:
        print(f"[DEBUG] >>> HTML CONTENT LENGTH: {len(result['data']['html'])}")
    if 'text' in result['data']:
        print(f"[DEBUG] >>> TEXT CONTENT LENGTH: {len(result['data']['text'])}")
        
    return ReceivedEmailDetail(**result["data"])


@router.post("/send-reply")
async def send_reply(
    lead_id: str,
    subject: str,
    body: str,
    db: AsyncSession = Depends(get_db),
):
    """Send a manual reply to a lead from the dashboard."""
    from uuid import UUID
    from app.models.lead import Lead
    from app.models.event import EmailEvent
    from app.integrations.sendgrid import EmailClient
    from datetime import datetime
    
    # Get lead
    from sqlalchemy import select
    stmt = select(Lead).where(Lead.id == UUID(lead_id))
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Send email via SendGrid/Resend
    client = EmailClient()
    send_result = await client.send_email(
        to_email=lead.email,
        subject=subject,
        body=body,
        reply_to=None,  # Use default from email
    )
    
    if not send_result.get("success"):
        raise HTTPException(status_code=500, detail=f"Failed to send email: {send_result.get('error')}")
    
    # Create EmailEvent for tracking
    event = EmailEvent(
        lead_id=UUID(lead_id),
        event_type="sent",
        title=subject,
        body=body,
        sendgrid_message_id=send_result.get("message_id"),
        touch_number=0,  # Manual reply, not part of sequence
    )
    db.add(event)
    await db.commit()
    
    print(f"[DEBUG] >>> Manual reply sent to {lead.email}: {subject}")
    
    return {
        "status": "success",
        "message": "Reply sent successfully",
        "message_id": send_result.get("message_id")
    }