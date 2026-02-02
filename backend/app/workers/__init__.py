"""Celery worker configuration."""
from celery import Celery

from app.config import settings

celery_app = Celery(
    "ai_sales_agent",
    broker=settings.get_redis_url,
    backend=settings.get_redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max per task
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# Periodic tasks (Beat schedule)
celery_app.conf.beat_schedule = {
    "check-staleness-every-day": {
        "task": "research.check_staleness",
        "schedule": 86400.0, # Every 24 hours
    },
    "check-followups-every-5-min": {
        "task": "send.check_followups",
        "schedule": 300.0, # Every 5 minutes for testing
    },
    "process-scheduled-sends": {
        "task": "send.process_scheduled",
        "schedule": 300.0, # Every 5 minutes
    },
    "check-replies-every-5-min": {
        "task": "send.check_replies",
        "schedule": 300.0, # Every 5 minutes
    }
}

# Import task modules to ensure registration
import app.workers.research_tasks
import app.workers.send_tasks
