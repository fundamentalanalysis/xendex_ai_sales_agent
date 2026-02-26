"""In Sequence API endpoints."""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_db
from app.models.in_sequence import Campaign as Sequence, CampaignLead as SequenceLead
from app.models.lead import Lead
from app.schemas.in_sequence import (
    SequenceCreate,
    SequenceUpdate,
    SequenceResponse,
    SequenceDetailResponse,
    SequenceListResponse,
    AddLeadsToSequence,
)
from app.models.draft import Draft
from app.engine.draft_generator import DraftGenerator
from app.engine.strategy import StrategyEngine
from datetime import datetime, timedelta

router = APIRouter()


@router.post("", response_model=SequenceResponse, status_code=201)
async def create_sequence(
    sequence_in: SequenceCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new sequence."""
    sequence = Sequence(**sequence_in.model_dump())
    db.add(sequence)
    await db.flush()
    await db.refresh(sequence)
    
    return sequence


@router.get("", response_model=SequenceListResponse)
async def list_sequences(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    type: str = Query("user", pattern="^(user|system|all)$"),
    db: AsyncSession = Depends(get_db),
):
    """List sequences with pagination.
    
    Args:
        type: 'user' (default) hides system sequences. 'system' shows only system sequences. 'all' shows everything.
    """
    
    # Lazy Init System Sequences
    if type == "system":
        # Check/Create Default (Auto)
        stmt = select(Sequence).where(Sequence.external_id == "DEFAULT-FOLLOWUP")
        result = await db.execute(stmt)
        default_seq = result.scalar_one_or_none()
        
        if not default_seq:
            default_sequence = Sequence(
                external_id="DEFAULT-FOLLOWUP",
                name="Follow-up Sequence",
                description="Auto-created sequence for managing follow-up sequences",
                sequence_touches=4,
                touch_delays=[3, 3, 3],
                status="active",
                template_type="user" 
            )
            db.add(default_sequence)
            
        await db.commit()

    stmt = select(Sequence)
    count_stmt = select(func.count(Sequence.id))
    
    # Filter by type
    from sqlalchemy import or_
    if type == "user":
        # Hide System Sequences
        stmt = stmt.where(
            or_(
                Sequence.external_id.is_(None),
                ~Sequence.external_id.in_(["DEFAULT-FOLLOWUP", "MANUAL-FOLLOWUP"])
            )
        )
        count_stmt = count_stmt.where(
            or_(
                Sequence.external_id.is_(None),
                ~Sequence.external_id.in_(["DEFAULT-FOLLOWUP", "MANUAL-FOLLOWUP"])
            )
        )
    elif type == "system":
        # Show ONLY System Sequences
        stmt = stmt.where(Sequence.external_id.in_(["DEFAULT-FOLLOWUP", "MANUAL-FOLLOWUP"]))
        count_stmt = count_stmt.where(Sequence.external_id.in_(["DEFAULT-FOLLOWUP", "MANUAL-FOLLOWUP"]))
    # else 'all' -> no filter


    if status:
        stmt = stmt.where(Sequence.status == status)
        count_stmt = count_stmt.where(Sequence.status == status)
    
    # Get total
    total_result = await db.execute(count_stmt)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size).order_by(Sequence.created_at.desc()).options(selectinload(Sequence.campaign_leads))
    
    result = await db.execute(stmt)
    sequences = result.scalars().all()
    
    # Calculate stats for list view
    for sequence in sequences:
        leads = sequence.campaign_leads
        sequence.total_leads = len(leads)
        # Count 'sequencing' as active too
        sequence.active_leads = sum(1 for sl in leads if sl.status in ["active", "sequencing"])
        sequence.completed_leads = sum(1 for sl in leads if sl.status == "completed")
    
    return SequenceListResponse(
        items=sequences,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{sequence_id}", response_model=SequenceDetailResponse)
async def get_sequence(
    sequence_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get sequence with stats."""
    stmt = (
        select(Sequence)
        .options(selectinload(Sequence.campaign_leads))
        .where(Sequence.id == sequence_id)
    )
    result = await db.execute(stmt)
    sequence = result.scalar_one_or_none()
    
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")
    
    # Calculate stats
    sequence_leads = sequence.campaign_leads
    
    response = SequenceDetailResponse(
        **{c.name: getattr(sequence, c.name) for c in sequence.__table__.columns},
        total_leads=len(sequence_leads),
        pending_leads=sum(1 for sl in sequence_leads if sl.status == "pending"),
        active_leads=sum(1 for sl in sequence_leads if sl.status == "active"),
        completed_leads=sum(1 for sl in sequence_leads if sl.status == "completed"),
        stopped_leads=sum(1 for sl in sequence_leads if sl.status == "stopped"),
    )
    
    return response


@router.get("/{sequence_id}/leads")
async def list_sequence_leads(
    sequence_id: UUID,
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List leads in a specific sequence with their status."""
    stmt = (
        select(SequenceLead)
        .options(selectinload(SequenceLead.lead))
        .where(SequenceLead.campaign_id == sequence_id)
    )
    
    if status:
        stmt = stmt.where(SequenceLead.status == status)
    
    result = await db.execute(stmt)
    items = result.scalars().all()
    
    # Flatten/Transform for easier frontend use
    leads = []
    for sl in items:
        if not sl.lead: continue
        lead_dict = {
            "id": str(sl.lead_id),
            "first_name": sl.lead.first_name,
            "last_name": sl.lead.last_name,
            "email": sl.lead.email,
            "company_name": sl.lead.company_name,
            "sequence_lead_status": sl.status,
            "current_touch": sl.current_touch,
            "next_touch_at": sl.next_touch_at.isoformat() if sl.next_touch_at else None,
            "lead_status": sl.lead.status,
        }
        leads.append(lead_dict)
        
    return leads


@router.patch("/{sequence_id}", response_model=SequenceResponse)
async def update_sequence(
    sequence_id: UUID,
    sequence_in: SequenceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a sequence."""
    stmt = select(Sequence).where(Sequence.id == sequence_id)
    result = await db.execute(stmt)
    sequence = result.scalar_one_or_none()
    
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")
        
    # PROTECT SYSTEM SEQUENCE
    if sequence.external_id == "DEFAULT-FOLLOWUP":
        # Block renaming or changing external_id
        if sequence_in.name and sequence_in.name != sequence.name:
            raise HTTPException(status_code=400, detail="Cannot rename system sequence.")
    
    update_data = sequence_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(sequence, field, value)
    
    await db.flush()
    await db.refresh(sequence)
    
    return sequence


@router.post("/{sequence_id}/leads", status_code=201)
async def add_leads_to_sequence(
    sequence_id: UUID,
    request: AddLeadsToSequence,
    db: AsyncSession = Depends(get_db),
):
    """Add leads to a sequence."""
    # Verify sequence exists
    stmt = select(Sequence).where(Sequence.id == sequence_id)
    result = await db.execute(stmt)
    sequence = result.scalar_one_or_none()
    
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")
    
    print(f"[DEBUG] >>> add_leads_to_sequence called for Sequence: {sequence_id}, Leads: {len(request.lead_ids)}")
    added = 0
    skipped = 0
    
    for lead_id in request.lead_ids:
        # Check if lead exists
        lead_stmt = select(Lead).where(Lead.id == lead_id)
        lead_result = await db.execute(lead_stmt)
        lead = lead_result.scalar_one_or_none()
        
        if not lead:
            skipped += 1
            continue
        
        # Check if already in sequence
        existing_stmt = select(SequenceLead).where(
            SequenceLead.campaign_id == sequence_id,
            SequenceLead.lead_id == lead_id,
        )
        existing_result = await db.execute(existing_stmt)
        if existing_result.scalars().first():
            skipped += 1
            continue
        
        # Add to sequence
        sequence_lead = SequenceLead(
            campaign_id=sequence_id,
            lead_id=lead_id,
            status="pending",
        )
        db.add(sequence_lead)
        
        # Status logic: New workflow
        if lead.status == "qualified":
            # Lead added to sequence but hasn't sent Touch 1 yet
            # Orchestrator will handle creating the Touch 1 draft
            pass
        elif lead.status == "contacted":
            # Step 1 complete! Mark as ready for Step 2+
            lead.status = "contacted"
            sequence_lead.status = "ready"
            print(f"[DEBUG] >>> Lead {lead.company_name} marked as READY for sequence.")
        
        added += 1
    
    await db.commit()
    print(f"[DEBUG] >>> Commit complete. Added: {added}, Skipped: {skipped}")
    
    # Trigger orchestrator if sequence is active
    if sequence.status == "active":
        from app.workers.send_tasks import run_orchestrator_task
        print(f"[DEBUG] >>> TRIGGERING ORCHESTRATOR from add_leads (Sequence: {sequence_id})")
        run_orchestrator_task.delay(str(sequence_id))
    
    return {"added": added, "skipped": skipped}


@router.post("/{sequence_id}/start", status_code=200)
async def start_sequence(
    sequence_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Start a sequence."""
    stmt = select(Sequence).where(Sequence.id == sequence_id)
    result = await db.execute(stmt)
    sequence = result.scalar_one_or_none()
    
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")
    
    # If not active, activate it
    if sequence.status != "active":
        sequence.status = "active"
    
    # Update all leads in this sequence to "sequencing" status
    sequence_leads_stmt = select(SequenceLead).where(SequenceLead.campaign_id == sequence_id)
    sequence_leads_result = await db.execute(sequence_leads_stmt)
    sequence_leads = sequence_leads_result.scalars().all()
    
    for sequence_lead in sequence_leads:
        sequence_lead.status = "active"
        lead_stmt = select(Lead).where(Lead.id == sequence_lead.lead_id)
        lead_result = await db.execute(lead_stmt)
        lead = lead_result.scalar_one_or_none()
        
        if lead and lead.status not in ["replied", "converted", "disqualified"]:
            if lead.status == "contacted":
                lead.status = "sequencing"
                # Schedule Touch 2
                from app.workers.send_tasks import follow_up_task
                # TEST MODE: Treat touch_delays value as MINUTES
                delay_minutes = sequence.touch_delays[0] if sequence.touch_delays else 2
                countdown = delay_minutes * 60
                
                follow_up_task.apply_async(
                    args=[str(lead.id), datetime.utcnow().isoformat(), 1, str(sequence.id)],
                    countdown=countdown
                )
            else:
                lead.status = "sequencing" # For qualified leads
    
    await db.commit()
    print(f"[DEBUG] >>> Sequence {sequence_id} started. Triggering orchestrator...")
    
    # Trigger sequence orchestrator
    from app.workers.send_tasks import run_orchestrator_task
    run_orchestrator_task.delay(str(sequence_id))
    
    return {"status": "started", "sequence_id": str(sequence_id)}


@router.post("/{sequence_id}/pause", status_code=200)
async def pause_sequence(
    sequence_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Pause a sequence."""
    stmt = select(Sequence).where(Sequence.id == sequence_id)
    result = await db.execute(stmt)
    sequence = result.scalar_one_or_none()
    
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")
    
    sequence.status = "paused"
    await db.flush()
    
    return {"status": "paused", "sequence_id": str(sequence_id)}


@router.delete("/{sequence_id}", status_code=204)
async def delete_sequence(
    sequence_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a sequence."""
    # Check if sequence exists
    stmt = select(Sequence).where(Sequence.id == sequence_id)
    result = await db.execute(stmt)
    sequence = result.scalar_one_or_none()
    
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")
    
    # Check if sequence is active
    if sequence.status == "active":
        raise HTTPException(status_code=400, detail="Cannot delete an active sequence. Pause or complete it first.")

    # Delete associated SequenceLead entries
    from sqlalchemy import delete
    await db.execute(
        delete(SequenceLead).where(SequenceLead.campaign_id == sequence_id)
    )

    # Delete the sequence
    await db.delete(sequence)
    await db.commit()
    
    return None


@router.post("/{sequence_id}/leads/{lead_id}/trigger", status_code=200)
async def trigger_followup(
    sequence_id: UUID,
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Trigger/Get follow-up draft for a lead in a sequence."""
    # 1. Verify SequenceLead exists
    sl_stmt = select(SequenceLead).where(
        and_(
            SequenceLead.campaign_id == sequence_id,
            SequenceLead.lead_id == lead_id
        )
    ).options(selectinload(SequenceLead.lead).selectinload(Lead.intelligence))
    result = await db.execute(sl_stmt)
    sl = result.scalars().first()
    
    if not sl:
        raise HTTPException(status_code=404, detail="Lead not found in this sequence")
    
    lead = sl.lead
    
    sequence_stmt = select(Sequence).where(Sequence.id == sequence_id)
    sequence_result = await db.execute(sequence_stmt)
    sequence = sequence_result.scalar_one_or_none()
    
    # 2. Check for existing 'pending' follow-up draft
    # touch_number for follow-up is sl.current_touch + 1
    next_touch = sl.current_touch + 1
    
    # Validation: Respect Sequence Limit
    # Logic: We treat sequence_touches as "Number of Followups" in inclusive mode (Limit 3 -> 4 touches)
    # So max permitted touch is sequence_touches + 1
    limit = (sequence.sequence_touches or 3) + 1
    
    if next_touch > limit:
         raise HTTPException(status_code=400, detail=f"Sequence complete. Max {limit} touches allowed.")

    if next_touch == 1:
        # If it's touch 1, maybe they were added to sequence without initial email
         pass
         
    draft_stmt = select(Draft).where(
        and_(
            Draft.lead_id == lead_id,
            Draft.campaign_id == sequence_id,
            Draft.touch_number == next_touch,
            Draft.status == "pending"
        )
    )
    result = await db.execute(draft_stmt)
    draft = result.scalar_one_or_none()
    
    if draft:
        return draft

    # 3. Generate new draft if not exists
    try:
        generator = DraftGenerator()
        strategy_engine = StrategyEngine()
        
        from app.api.routes.research import _your_company_cache
        your_company = _your_company_cache or {"services": [], "positioning": "We help companies succeed"}
        
        lead_data = {
            "first_name": lead.first_name or "there",
            "last_name": lead.last_name or "",
            "company_name": lead.company_name,
            "email": lead.email,
            "persona": lead.persona,
            "personalization_mode": lead.personalization_mode,
        }
        
        intel = lead.intelligence
        # Safety for missing intel
        if not intel:
            # Create dummy intel or fail
            intel_dict = {}
        else:
            intel_dict = {
                "industry": intel.lead_offerings[0] if intel and intel.lead_offerings else "",
                "pain_indicators": intel.lead_pain_indicators or [],
                "buying_signals": intel.lead_buying_signals or [],
                "triggers": intel.triggers or [],
                "linkedin_data": {
                    "role": intel.linkedin_role,
                    "seniority": intel.linkedin_seniority,
                    "topics_30d": intel.linkedin_topics_30d or [],
                }
            }
        
        strategy = strategy_engine.determine_strategy(
            lead_intelligence=intel_dict,
            linkedin_data=intel_dict.get("linkedin_data"),
            triggers=intel_dict.get("triggers"),
            personalization_mode=lead_data["personalization_mode"],
        )
        
        draft_res = await generator.generate_draft(
            lead_data=lead_data,
            intelligence=intel_dict,
            your_company=your_company,
            strategy=strategy,
            touch_number=next_touch,
        )
        
        draft = Draft(
            lead_id=lead.id,
            campaign_id=sequence_id,
            touch_number=next_touch,
            subject_options=draft_res.get("subject_options"),
            body=draft_res.get("body", ""),
            strategy=strategy,
            evidence=draft_res.get("evidence"),
            personalization_mode=lead_data["personalization_mode"],
            status="pending",
        )
        db.add(draft)
        await db.commit()
        await db.refresh(draft)
        
        return draft
    except Exception as e:
        print(f"[ERROR] Failed to generate follow-up draft: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate follow-up: {str(e)}")


@router.post("/{sequence_id}/leads/{lead_id}/approve", status_code=200)
async def approve_followup(
    sequence_id: UUID,
    lead_id: UUID,
    request: dict, # {draft_id, subject, body}
    db: AsyncSession = Depends(get_db),
):
    """Approve and Send follow-up email, and schedule the next ones."""
    from app.workers.send_tasks import send_email_task
    
    draft_id = UUID(request.get("draft_id"))
    stmt = select(Draft).where(Draft.id == draft_id)
    result = await db.execute(stmt)
    draft = result.scalar_one_or_none()
    
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
        
    # Update draft
    draft.status = "approved"
    draft.selected_subject = request.get("subject")
    draft.body = request.get("body")
    draft.approved_at = datetime.utcnow()
    
    # Update SequenceLead
    sl_stmt = select(SequenceLead).where(
        and_(
            SequenceLead.campaign_id == sequence_id,
            SequenceLead.lead_id == lead_id
        )
    )
    sl_res = await db.execute(sl_stmt)
    sl = sl_res.scalars().first()
    if sl:
        sl.status = "active"
        sl.current_touch = draft.touch_number
        # Schedule next touch date in DB (for display)
        sequence_stmt = select(Sequence).where(Sequence.id == sequence_id)
        seq_res = await db.execute(sequence_stmt)
        sequence = seq_res.scalar_one_or_none()
        
        delay_days = 3
        if sequence and sequence.touch_delays and len(sequence.touch_delays) >= draft.touch_number:
            delay_days = sequence.touch_delays[draft.touch_number - 1]
            
        sl.next_touch_at = datetime.utcnow() + timedelta(days=delay_days)

    await db.commit()
    
    # Send Touch 2 immediately
    send_email_task.delay(str(draft.id))
    
    # NOW trigger the automated follow-up chain (Touch 3, 4, etc.)
    # This is where the automation starts!
    if sequence:
        touches_limit = sequence.sequence_touches or 3
        
        # Only schedule next touch if we haven't reached the limit
        if draft.touch_number < touches_limit:
            from app.workers.send_tasks import follow_up_task
            
            # Get delay for next touch (Touch 3)
            delay_minutes = 1  # Default 1 minute for testing
            if sequence.touch_delays and len(sequence.touch_delays) >= draft.touch_number:
                delay_minutes = sequence.touch_delays[draft.touch_number - 1]
            
            countdown = delay_minutes * 60
            
            # Schedule Touch 3
            follow_up_task.apply_async(
                args=[str(lead_id), datetime.utcnow().isoformat(), draft.touch_number, str(sequence_id)],
                countdown=countdown
            )
            print(f"[DEBUG] >>> AUTOMATED SEQUENCE STARTED: Touch {draft.touch_number + 1} scheduled in {delay_minutes}m")
    
    return {"status": "sent", "draft_id": str(draft.id)}


# ============== Backward Compatibility Aliases ==============
# These allow existing code to work during transition
create_campaign = create_sequence
list_campaigns = list_sequences
get_campaign = get_sequence
list_campaign_leads = list_sequence_leads
update_campaign = update_sequence
add_leads_to_campaign = add_leads_to_sequence
start_campaign = start_sequence
pause_campaign = pause_sequence
delete_campaign = delete_sequence
