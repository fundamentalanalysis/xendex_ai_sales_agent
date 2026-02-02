"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.config import settings
from app.api.routes import leads, in_sequence, drafts, research, analytics, health, templates, webhooks, debug, emails
from app.dependencies import init_db

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting AI Sales Agent API")
    await init_db()
    yield
    logger.info("Shutting down AI Sales Agent API")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AI Sales Agent API",
        description="Production-ready multi-agent sales outreach system",
        version="0.1.0",
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register routes
    app.include_router(health.router, tags=["Health"])
    app.include_router(leads.router, prefix="/api/v1/leads", tags=["Leads"])
    app.include_router(research.router, prefix="/api/v1/research", tags=["Research"])
    app.include_router(in_sequence.router, prefix="/api/v1/in-sequence", tags=["In Sequence"])
    app.include_router(drafts.router, prefix="/api/v1/drafts", tags=["Drafts"])
    app.include_router(templates.router, prefix="/api/v1/templates", tags=["Templates"])
    app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
    app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])
    app.include_router(debug.router, prefix="/api/v1/debug", tags=["Debug"])
    app.include_router(emails.router, prefix="/api/v1", tags=["Emails"])

    # PROD: Serve Frontend Static Files (Single Docker Image)
    import os
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    # In Docker, we'll put build files in /app/static
    # Locally, we might check if ../frontend/dist exists (optional, but good for testing)
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    
    # If the directory exists (it will in Docker), mount it
    if os.path.exists(static_dir):
        logger.info(f"Serving static files from {static_dir}")
        
        # Mount assets/js/css
        app.mount("/assets", StaticFiles(directory=f"{static_dir}/assets"), name="assets")
        
        # Catch-all for SPA (serves index.html)
        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            # API routes are already handled above, so this catches everything else
            # If it's a file request that wasn't found in assets, it might be favicon.ico etc.
            potential_file = os.path.join(static_dir, full_path)
            if os.path.isfile(potential_file):
                return FileResponse(potential_file)
                
            # Otherwise return index.html for React Router
            return FileResponse(os.path.join(static_dir, "index.html"))
    else:
        logger.warning(f"Static directory not found at {static_dir}. Running in API-only mode (or local dev).")
    
    return app


app = create_app()
