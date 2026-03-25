from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "calligraphy_recognition",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_track_started=True,
    result_expires=3600,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=False,
)

celery_app.autodiscover_tasks(["app.modules.pantianshou_composition"])

