from __future__ import annotations

import os
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()


# 캠프 일정 데이터
CAMP_SCHEDULE = [
    {
        "day": 1,
        "date": "2026-03-14",
        "date_end": "2026-03-22",
        "title": "온라인 OT + 핸즈온 실습",
        "type": "online",
        "duration": "~4시간 (주말 중 자율)",
        "deliverable": None,
    },
    {
        "day": 2,
        "date": "2026-03-23",
        "date_end": None,
        "title": "Day 2 학습 + 과제 제출",
        "type": "online",
        "duration": "종일",
        "deliverable": "과제 제출",
    },
    {
        "day": 3,
        "date": "2026-03-24",
        "date_end": None,
        "title": "Day 3 학습 + 과제 제출",
        "type": "online",
        "duration": "종일",
        "deliverable": "과제 제출",
    },
    {
        "day": 4,
        "date": "2026-03-25",
        "date_end": None,
        "title": "Day 4 학습 + 과제 제출",
        "type": "online",
        "duration": "종일",
        "deliverable": "과제 제출",
    },
    {
        "day": 5,
        "date": "2026-03-27",
        "date_end": None,
        "title": "최종 산출물 제출 및 공유",
        "type": "offline",
        "duration": "종일",
        "deliverable": "최종 산출물 제출",
    },
]


class Config:
    # Slack
    SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
    SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
    SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

    # Anthropic
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    # Google OAuth2
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")
    SESSION_SECRET = os.getenv("SESSION_SECRET", "sentbe-camp-secret-change-me")

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///camp.db")

    # Camp info
    CAMP_NAME = os.getenv("CAMP_NAME", "Sentbe AI Native Camp")
    CAMP_START_DATE = date(2026, 3, 14)
    CAMP_END_DATE = date(2026, 3, 27)
    DEFAULT_CHANNEL = os.getenv("DEFAULT_CHANNEL", "general")

    @classmethod
    def days_remaining(cls) -> int:
        delta = cls.CAMP_END_DATE - date.today()
        return max(0, delta.days)

    @classmethod
    def camp_day(cls) -> int:
        """현재 캠프 Day를 반환합니다 (일정 기반)."""
        today = date.today()
        for item in CAMP_SCHEDULE:
            d = date.fromisoformat(item["date"])
            d_end = date.fromisoformat(item["date_end"]) if item["date_end"] else d
            if d <= today <= d_end:
                return item["day"]
        # 캠프 종료 후
        if today > cls.CAMP_END_DATE:
            return 5
        # 캠프 시작 전
        return 0

    @classmethod
    def progress_percent(cls) -> float:
        total = len(CAMP_SCHEDULE)
        current = cls.camp_day()
        if current == 0:
            return 0.0
        return min(100.0, (current / total) * 100)

    @classmethod
    def today_schedule(cls) -> dict | None:
        """오늘의 일정을 반환합니다."""
        today = date.today()
        for item in CAMP_SCHEDULE:
            d = date.fromisoformat(item["date"])
            d_end = date.fromisoformat(item["date_end"]) if item["date_end"] else d
            if d <= today <= d_end:
                return item
        return None

    @classmethod
    def next_schedule(cls) -> dict | None:
        """다음 일정을 반환합니다."""
        today = date.today()
        for item in CAMP_SCHEDULE:
            d = date.fromisoformat(item["date"])
            if d > today:
                return item
        return None

    @classmethod
    def get_schedule(cls) -> list[dict]:
        """전체 일정을 반환합니다."""
        return CAMP_SCHEDULE
