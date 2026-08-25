"""
예측 기반 알림 배치(app/services/notification_batch.py)를 매일 정해진 시각에 돌리는 스케줄러.

rate_limit.py, blood_predictor.py 캐시와 같은 이유로 이 프로젝트는 아직 단일 프로세스
배포를 가정한다 - 그래서 별도 워커/큐(Celery 등) 없이 앱 프로세스 안에서 APScheduler로
돌린다. uvicorn을 여러 워커로 띄우면 배치가 워커 수만큼 중복 실행되니, 그때는 이 방식을
외부 스케줄러(예: cron이 API를 호출)나 워커 중 하나만 켜는 방식으로 바꿔야 한다.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.services.notification_batch import run_notification_batch

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        run_notification_batch,
        trigger=CronTrigger(hour=settings.notification_batch_hour, minute=0),
        id="blood_shortage_notification_batch",
        # 배치 실행 중 앱이 재시작되는 등으로 놓친 실행은 그냥 건너뛴다 - 밀린 만큼 몰아서
        # 실행하면 하루에 여러 번 알림이 나갈 수 있다.
        misfire_grace_time=None,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("알림 배치 스케줄러 시작 (매일 %d시)", settings.notification_batch_hour)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
