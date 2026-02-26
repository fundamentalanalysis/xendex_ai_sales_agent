from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class DebugLogRequest(BaseModel):
    message: str
    level: str = "info"

import structlog
logger = structlog.get_logger()

@router.post("/log")
async def log_from_frontend(request: DebugLogRequest):
    """Log a message from the frontend to the backend terminal."""
    logger.info("Frontend Log", level=request.level.upper(), message=request.message)
    return {"status": "logged"}
