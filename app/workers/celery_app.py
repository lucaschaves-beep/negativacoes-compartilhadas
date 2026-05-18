from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "negativacoes",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.workers.tasks.process_card": {"queue": "cards"},
        "app.workers.tasks.analyze_attachment": {"queue": "attachments"},
    },
)
