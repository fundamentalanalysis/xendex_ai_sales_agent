"""Celery app instance for imports."""
from app.workers import celery_app

__all__ = ["celery_app"]
