from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from slack_sdk import WebClient

from services.announce_service import get_pending_announcements, send_announcement
from models.database import SessionLocal, Announcement


scheduler = BackgroundScheduler()


def check_scheduled_announcements(slack_client: WebClient):
    """예약된 공지를 확인하고 발송합니다."""
    pending = get_pending_announcements()
    for announcement in pending:
        send_announcement(
            slack_client=slack_client,
            title=announcement.title,
            content=announcement.content,
            channel=announcement.channel,
        )
        # 원본 예약 레코드 업데이트
        db = SessionLocal()
        try:
            record = db.query(Announcement).get(announcement.id)
            if record:
                record.is_sent = True
                record.sent_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()


def start_scheduler(slack_client: WebClient):
    """스케줄러를 시작합니다."""
    scheduler.add_job(
        check_scheduled_announcements,
        "interval",
        minutes=1,
        args=[slack_client],
        id="check_scheduled",
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler():
    """스케줄러를 중지합니다."""
    if scheduler.running:
        scheduler.shutdown()
