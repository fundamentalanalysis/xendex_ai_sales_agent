import sys
import asyncio

if sys.platform == 'win32':
    # This must be done BEFORE the first loop is created
    # Uvicorn on Windows defaults to SelectorEventLoop which breaks subprocesses (Playwright)
    # We try to force ProactorEventLoopPolicy
    policy = asyncio.get_event_loop_policy()
    if not isinstance(policy, asyncio.WindowsProactorEventLoopPolicy):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass

import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.config import settings
from app.logging import setup_logging
from app.api.routes import leads, in_sequence, drafts, research, analytics, health, templates, webhooks, debug, emails, scoring
from app.dependencies import init_db, engine

# Initialize logging before logger creation
setup_logging()
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    loop = asyncio.get_running_loop()
    loop_type = type(loop).__name__
    
    if sys.platform == 'win32' and loop_type != 'ProactorEventLoop':
        logger.warning(
            "⚠️  DETECTION: Windows is using SelectorEventLoop instead of ProactorEventLoop!",
            hint="Subprocesses (like Playwright/LinkedIn scraper) will CRASH. Run uvicorn with --loop asyncio if this continues."
        )
        
    logger.info("🚀 Starting AI Sales Agent API", 
                server_time=datetime.utcnow().isoformat(),
                event_loop=loop_type)
    await init_db()
    
    # Check Redis connection
    try:
        import redis
        with redis.from_url(settings.get_redis_url) as r:
            r.ping()
            logger.info("✅ Redis Connection: SUCCESS")
    except Exception as e:
        logger.error("❌ Redis Connection: FAILED", error=str(e))
        
    yield
    
    logger.info("Shutting down AI Sales Agent API")
    await engine.dispose()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AI Sales Agent API",
        description="Backend API for AI-powered sales outreach",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    app.include_router(leads.router, prefix="/api/v1/leads", tags=["Leads"])
    app.include_router(in_sequence.router, prefix="/api/v1/in-sequence", tags=["Campaigns"])
    app.include_router(drafts.router, prefix="/api/v1/drafts", tags=["Drafts"])
    app.include_router(research.router, prefix="/api/v1/research", tags=["Research"])
    app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
    app.include_router(health.router, prefix="/api/v1/health", tags=["Health"])
    app.include_router(templates.router, prefix="/api/v1/templates", tags=["Templates"])
    app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
    app.include_router(debug.router, prefix="/api/v1/debug", tags=["Debug"])
    app.include_router(emails.router, prefix="/api/v1/emails", tags=["Emails"])
    app.include_router(scoring.router, prefix="/api/v1", tags=["Scoring"])

    @app.get("/")
    async def root():
        return {
            "message": "AI Sales Agent API is running",
            "docs": "/docs",
            "version": "1.0.0",
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    # Use config from server
    logger.info("Backend running in API-only mode. Frontend served on port 3000.")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
