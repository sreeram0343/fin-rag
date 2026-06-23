from celery import Celery
from finrag.core.config import settings

celery_app = Celery(
    "finrag",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["finrag.tasks.document_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"max_retries": 3, "interval_start": 0.2, "interval_step": 0.2}
)
