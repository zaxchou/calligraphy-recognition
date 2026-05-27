from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "molin_wiki",
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

# Import tasks directly (autodiscover not working reliably)
from app.modules.pantianshou_composition.tasks import analyze_composition  # noqa: F401, E402

