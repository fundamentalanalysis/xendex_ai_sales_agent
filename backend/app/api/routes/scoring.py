from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Optional, List
from datetime import datetime
import structlog
from uuid import UUID

from app.dependencies import get_db
from app.config import settings
from app.models.lead import Lead, LeadIntelligence
from app.engine.scoring_engine import MasterScoringEngine, LeadScores, SimpleDataExtractor

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/scoring", tags=["scoring"])


def safe_int(value, default=0):
    """
    Convert value to int safely, handling None and type errors.
    
    ✅ Prevents: TypeError: '<' not supported between instances of 'NoneType' and 'int'
    """
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        logger.warning(f"Could not convert {value} to int, using default {default}")
        return default


def safe_comparison(value, threshold, default=False):
    """
    Safely compare value to threshold, handling None values.
    
    Usage:
        if safe_comparison(lead.score, 50, default=False):
            print("Score is >= 50")
    """
    if value is None:
        return default
    try:
        return value >= threshold
    except TypeError:
        return default



@router.get("/{lead_id}/recalculate")
async def recalculate_scores(lead_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Recalculate lead scores with comprehensive error handling.
    """
    try:
        stmt = select(Lead).where(Lead.id == lead_id)
        result = await db.execute(stmt)
        lead = result.scalar_one_or_none()
        
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        logger.info(f"Starting score recalculation for lead {lead_id}")
            
        intel_stmt = select(LeadIntelligence).where(LeadIntelligence.lead_id == lead_id)
        intel_res = await db.execute(intel_stmt)
        intel = intel_res.scalars().first()
        
        if not intel:
            logger.warning(f"No intelligence data found for lead {lead_id}, using minimal defaults")
        
        engine = MasterScoringEngine(qualification_threshold=settings.qualification_threshold)
        
        try:
            fit_inputs = SimpleDataExtractor.extract_fit_inputs(lead, intel)
            readiness_inputs = SimpleDataExtractor.extract_readiness_inputs(lead, intel)
            intent_inputs = SimpleDataExtractor.extract_intent_inputs(lead, intel)
            
            logger.info(
                f"Extracted inputs for lead {lead_id}",
                extra={
                    "fit_inputs": fit_inputs,
                    "readiness_inputs": readiness_inputs,
                    "intent_inputs": intent_inputs
                }
            )
        except Exception as e:
            logger.error(f"Failed to extract inputs for lead {lead_id}: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Input extraction failed: {str(e)}")
        
        try:
            combined_inputs = {**fit_inputs, **readiness_inputs, **intent_inputs}
            scores: LeadScores = engine.calculate_all_scores(**combined_inputs)
        except TypeError as e:
            if "not supported between instances of 'NoneType'" in str(e):
                logger.error(
                    f"NoneType comparison error in scoring engine: {str(e)}",
                    extra={
                        "lead_id": lead_id,
                        "fit_inputs": fit_inputs,
                        "readiness_inputs": readiness_inputs,
                        "intent_inputs": intent_inputs
                    }
                )
                raise HTTPException(
                    status_code=500,
                    detail="Scoring engine encountered invalid data (None values). Please verify lead intelligence data."
                )
            raise
        except Exception as e:
            logger.error(f"Scoring calculation failed for lead {lead_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")
        
        try:
            lead.fit_score = scores.fit_score
            lead.readiness_score = scores.readiness_score
            lead.intent_score = scores.intent_score
            lead.composite_score = scores.composite_score
            lead.status = scores.qualification_status
            
            await db.commit()
            await db.refresh(lead)
            
            logger.info(
                f"Scores saved for lead {lead_id}",
                extra={
                    "fit_score": scores.fit_score,
                    "readiness_score": scores.readiness_score,
                    "intent_score": scores.intent_score,
                    "composite_score": scores.composite_score
                }
            )
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to save scores for lead {lead_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to save scores: {str(e)}")
        
        try:
            validations = engine.validate_scores(scores)
        except Exception as e:
            logger.warning(f"Score validation failed for lead {lead_id}: {str(e)}")
            validations = {}
        
        return {
            "lead_id": lead_id,
            "company_name": lead.company_name,
            "contact_name": f"{lead.first_name} {lead.last_name}",
            "fit_score": scores.fit_score,
            "readiness_score": scores.readiness_score,
            "intent_score": scores.intent_score,
            "composite_score": scores.composite_score,
            "status": scores.qualification_status,
            "fit_breakdown": {
                "components": scores.fit_breakdown.components,
                "percentage": scores.fit_breakdown.percentage,
                "notes": scores.fit_breakdown.notes
            },
            "readiness_breakdown": {
                "components": scores.readiness_breakdown.components,
                "percentage": scores.readiness_breakdown.percentage,
                "notes": scores.readiness_breakdown.notes
            },
            "intent_breakdown": {
                "components": scores.intent_breakdown.components,
                "percentage": scores.intent_breakdown.percentage,
                "notes": scores.intent_breakdown.notes
            },
            "recalculated_at": datetime.utcnow().isoformat(),
            "validations": validations,
            "validation_passed": all(validations.values()) if validations else False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error recalculating scores for {lead_id}: {str(e)}",
            error_type=type(e).__name__,
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
