"""Sequence tasks for automated lead management."""
import asyncio
from datetime import datetime, timedelta
from uuid import UUID
import structlog
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.workers import celery_app
from app.config import settings
from app.models.lead import Lead
from app.models.event import EmailEvent
from app.models.in_sequence import Campaign, CampaignLead
from app.models.draft import Draft

logger = structlog.get_logger()

@celery_app.task(name="sequence.move_stale_leads")
def move_stale_leads_task():
    """Move leads with no reply after 3 days to sequence."""
    async def _run():
        engine = create_async_engine(settings.get_database_url, pool_pre_ping=True)
        async_session = async_sessionmaker(engine, class_=AsyncSession)
        
        try:
            async with async_session() as db:
                # 1. Ensure DEFAULT-FOLLOWUP campaign exists
                stmt = select(Campaign).where(Campaign.external_id == "DEFAULT-FOLLOWUP")
                result = await db.execute(stmt)
                campaign = result.scalar_one_or_none()
                
                if not campaign:
                    campaign = Campaign(
                        external_id="DEFAULT-FOLLOWUP",
                        name="Follow-up Sequence",
                        description="Auto-created campaign for managing follow-up sequences",
                        sequence_touches=4,
                        touch_delays=[3, 3, 3], # 3 days between each
                        status="active",
                        template_type="user"
                    )
                    db.add(campaign)
                    await db.flush()
                
                # 2. Find leads in 'contacted' status for more than 3 days
                three_days_ago = datetime.utcnow() - timedelta(days=3)
                # For demo/testing, we might use minutes or seconds, but user said 3 days
                # Let's keep it 3 days for production logic
                
                leads_stmt = select(Lead).where(
                    and_(
                        Lead.status == "contacted",
                        Lead.last_contacted_at <= three_days_ago
                    )
                )
                result = await db.execute(leads_stmt)
                leads = result.scalars().all()
                
                moved_count = 0
                for lead in leads:
                    # 3. Check for replies
                    reply_stmt = select(EmailEvent).where(
                        and_(
                            EmailEvent.lead_id == lead.id,
                            EmailEvent.event_type == "replied",
                            EmailEvent.created_at >= lead.last_contacted_at
                        )
                    )
                    reply_result = await db.execute(reply_stmt)
                    if reply_result.scalar_one_or_none():
                        # Already replied! Update status
                        lead.status = "replied"
                        continue
                    
                    # 4. Check if already in sequence campaign
                    cl_stmt = select(CampaignLead).where(
                        and_(
                            CampaignLead.campaign_id == campaign.id,
                            CampaignLead.lead_id == lead.id
                        )
                    )
                    cl_result = await db.execute(cl_stmt)
                    if cl_result.scalar_one_or_none():
                        continue
                        
                    # 5. Add to sequence
                    cl = CampaignLead(
                        campaign_id=campaign.id,
                        lead_id=lead.id,
                        status="pending" # 'pending' until trigger button is clicked
                    )
                    db.add(cl)
                    lead.status = "sequencing"
                    moved_count += 1
                    
                await db.commit()
                return {"moved": moved_count}
        finally:
            await engine.dispose()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(_run())
