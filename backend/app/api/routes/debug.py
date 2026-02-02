from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class DebugLogRequest(BaseModel):
    message: str
    level: str = "info"

@router.post("/log")
async def log_from_frontend(request: DebugLogRequest):
    """Log a message from the frontend to the backend terminal."""
    print(f"\n[FRONTEND LOG] [{request.level.upper()}] {request.message}")
    return {"status": "logged"}
