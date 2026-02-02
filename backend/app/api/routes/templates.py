"""Templates API endpoints."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.template import Template
from pydantic import BaseModel, Field
from typing import List

router = APIRouter()


# Schemas
class TemplateCreate(BaseModel):
    name: str = Field(..., max_length=255)
    type: str  # trigger-led, problem-hypothesis, case-study, quick-question
    touch_number: int = Field(1, ge=1, le=3)
    subject_template: str
    body_template: str
    required_variables: Optional[List[str]] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    type: Optional[str] = None
    touch_number: Optional[int] = Field(None, ge=1, le=3)
    subject_template: Optional[str] = None
    body_template: Optional[str] = None
    required_variables: Optional[List[str]] = None
    is_active: Optional[bool] = None


class TemplateResponse(BaseModel):
    id: UUID
    name: str
    type: str
    touch_number: int
    subject_template: str
    body_template: str
    required_variables: Optional[List[str]] = None
    times_used: int
    avg_open_rate: Optional[float] = None
    avg_reply_rate: Optional[float] = None
    is_active: bool
    
    class Config:
        from_attributes = True


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template(
    template_in: TemplateCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new template."""
    template = Template(**template_in.model_dump())
    db.add(template)
    await db.flush()
    await db.refresh(template)
    
    return template


@router.get("", response_model=List[TemplateResponse])
async def list_templates(
    type: Optional[str] = None,
    touch_number: Optional[int] = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """List templates with filtering."""
    stmt = select(Template)
    
    if type:
        stmt = stmt.where(Template.type == type)
    
    if touch_number:
        stmt = stmt.where(Template.touch_number == touch_number)
    
    if active_only:
        stmt = stmt.where(Template.is_active == True)
    
    stmt = stmt.order_by(Template.type, Template.touch_number)
    
    result = await db.execute(stmt)
    templates = result.scalars().all()
    
    return templates


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a template by ID."""
    stmt = select(Template).where(Template.id == template_id)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return template


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: UUID,
    template_in: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a template."""
    stmt = select(Template).where(Template.id == template_id)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    update_data = template_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)
    
    await db.flush()
    await db.refresh(template)
    
    return template


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a template (set inactive)."""
    stmt = select(Template).where(Template.id == template_id)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template.is_active = False
    await db.flush()


# Seed default templates
DEFAULT_TEMPLATES = [
    {
        "name": "Trigger-Led T1",
        "type": "trigger-led",
        "touch_number": 1,
        "subject_template": "{trigger_reference}",
        "body_template": """Hi {first_name},

I noticed {trigger_detail}. {insight_about_trigger}

We've helped companies like {similar_company} with {relevant_solution}.

{cta}

Best,
{signature}""",
        "required_variables": ["first_name", "trigger_detail", "cta"],
    },
    {
        "name": "Problem Hypothesis T1",
        "type": "problem-hypothesis",
        "touch_number": 1,
        "subject_template": "Quick thought on {pain_area}",
        "body_template": """Hi {first_name},

Many {persona_type}s at {company_type} companies tell us {common_pain}.

{how_we_help}

{proof_point}

{cta}

Best,
{signature}""",
        "required_variables": ["first_name", "pain_area", "cta"],
    },
    {
        "name": "Follow-up T2",
        "type": "follow_up",
        "touch_number": 2,
        "subject_template": "Re: {original_subject}",
        "body_template": """Hi {first_name},

Just circling back on my note from a few days ago.

{brief_reminder}

{new_value_add}

{cta}

Best,
{signature}""",
        "required_variables": ["first_name", "cta"],
    },
    {
        "name": "Breakup T3",
        "type": "breakup",
        "touch_number": 3,
        "subject_template": "Should I close your file?",
        "body_template": """Hi {first_name},

I've reached out a couple of times about {topic}.

If this isn't a priority right now, no worries at all.

If things change, feel free to reach out.

Best,
{signature}""",
        "required_variables": ["first_name", "topic"],
    },
]


@router.post("/seed", status_code=201)
async def seed_templates(
    db: AsyncSession = Depends(get_db),
):
    """Seed default templates if they don't exist."""
    created = 0
    
    for template_data in DEFAULT_TEMPLATES:
        # Check if exists
        stmt = select(Template).where(
            Template.name == template_data["name"],
            Template.type == template_data["type"],
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            continue
        
        template = Template(**template_data)
        db.add(template)
        created += 1
    
    await db.flush()
    
    return {"created": created, "templates": len(DEFAULT_TEMPLATES)}
