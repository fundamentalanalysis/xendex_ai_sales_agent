from celery import Celery
import structlog
from celery.signals import after_setup_logger, after_setup_task_logger
from app.config import settings
from app.logging import setup_logging

# Initialize logging for the main process
setup_logging()
logger = structlog.get_logger()

@after_setup_logger.connect
@after_setup_task_logger.connect
def setup_celery_logging(logger, **kwargs):
    """Ensure structlog is setup for Celery workers."""
    setup_logging()
    # Add a startup log to confirm it's working
    import structlog
    log = structlog.get_logger()
    log.info("Celery Worker Logging Initialized", mode="solo")

celery_app = Celery(
    "ai_sales_agent",
    broker=settings.get_redis_url,
    backend=settings.get_redis_url,
)

# Crucial for Windows logging and connection limits
celery_app.conf.update(
    worker_hijack_root_logger=False,
    worker_log_color=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max per task
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_pool_limit=1,
    redis_max_connections=2,
    worker_send_task_events=False,
    worker_enable_remote_control=False,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    broker_heartbeat=0, # Disable heartbeats to save connections
    redis_socket_timeout=30,
    redis_retry_on_timeout=True,
    task_ignore_result=True,
    result_persistent=False,
    worker_gossip=False,
    worker_mingle=False,
    worker_max_tasks_per_child=5,
)

# Automatic import of tasks
celery_app.autodiscover_tasks(["app.workers"])
