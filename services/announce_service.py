from __future__ import annotations

from datetime import datetime

from slack_sdk import WebClient
from sqlalchemy.orm import Session

from config import Config
from models.database import Announcement, SessionLocal


def send_announcement(
    slack_client: WebClient,
    title: str,
    content: str,
    channel: str | None = None,
    created_by: str | None = None,
    gcal_url: str | None = None,
) -> Announcement:
    """공지를 Slack에 발송하고 DB에 저장합니다."""
    channel = channel or Config.DEFAULT_CHANNEL

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📢 {title}", "emoji": True},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": content},
        },
    ]

    if gcal_url:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📅 Google 캘린더에 추가", "emoji": True},
                    "url": gcal_url,
                    "action_id": "open_gcal",
                },
            ],
        })

    blocks.extend([
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_{Config.CAMP_NAME} 운영팀 | {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
                }
            ],
        },
    ])

    result = slack_client.chat_postMessage(
        channel=channel, text=f"📢 {title}\n{content}", blocks=blocks
    )

    db = SessionLocal()
    try:
        announcement = Announcement(
            title=title,
            content=content,
            channel=channel,
            is_sent=True,
            sent_at=datetime.utcnow(),
            created_by=created_by,
            slack_ts=result["ts"],
        )
        db.add(announcement)
        db.commit()
        db.refresh(announcement)
        return announcement
    finally:
        db.close()


def schedule_announcement(
    title: str,
    content: str,
    scheduled_at: datetime,
    channel: str | None = None,
    created_by: str | None = None,
) -> Announcement:
    """공지를 예약합니다."""
    channel = channel or Config.DEFAULT_CHANNEL
    db = SessionLocal()
    try:
        announcement = Announcement(
            title=title,
            content=content,
            channel=channel,
            scheduled_at=scheduled_at,
            is_sent=False,
            created_by=created_by,
        )
        db.add(announcement)
        db.commit()
        db.refresh(announcement)
        return announcement
    finally:
        db.close()


def get_announcements(limit: int = 20) -> list[Announcement]:
    """최근 공지 목록을 조회합니다."""
    db = SessionLocal()
    try:
        return (
            db.query(Announcement)
            .order_by(Announcement.created_at.desc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()


def get_pending_announcements() -> list[Announcement]:
    """발송 대기 중인 예약 공지를 조회합니다."""
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        return (
            db.query(Announcement)
            .filter(
                Announcement.is_sent == False,
                Announcement.scheduled_at != None,
                Announcement.scheduled_at <= now,
            )
            .all()
        )
    finally:
        db.close()
