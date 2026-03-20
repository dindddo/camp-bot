"""Google Calendar 링크를 생성하는 서비스."""
from __future__ import annotations

from datetime import date
from urllib.parse import quote

from config import Config, CAMP_SCHEDULE


def build_gcal_url(
    title: str,
    start_date: str,
    end_date: str | None = None,
    description: str = "",
    location: str = "",
) -> str:
    """Google Calendar 이벤트 추가 URL을 생성합니다.

    Args:
        title: 이벤트 제목
        start_date: 시작일 (YYYY-MM-DD)
        end_date: 종료일 (YYYY-MM-DD), None이면 start_date와 동일
        description: 이벤트 설명
        location: 장소
    """
    end_date = end_date or start_date

    # Google Calendar는 all-day 이벤트의 end_date를 "다음 날"로 지정해야 함
    end_dt = date.fromisoformat(end_date)
    from datetime import timedelta
    end_next = (end_dt + timedelta(days=1)).isoformat().replace("-", "")
    start_fmt = start_date.replace("-", "")

    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{start_fmt}/{end_next}",
        "details": description,
    }
    if location:
        params["location"] = location

    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return f"https://calendar.google.com/calendar/render?{query}"


def get_day_calendar_url(day: int, assignment_summary: str = "") -> str | None:
    """특정 Day의 Google Calendar 링크를 생성합니다."""
    schedule = None
    for item in CAMP_SCHEDULE:
        if item["day"] == day:
            schedule = item
            break

    if not schedule:
        return None

    title = f"[{Config.CAMP_NAME}] Day {day} — {schedule['title']}"

    details_parts = [
        f"📅 {Config.CAMP_NAME} Day {day}",
        f"📋 {schedule['title']}",
    ]
    if schedule.get("deliverable"):
        details_parts.append(f"📝 {schedule['deliverable']}")
    if assignment_summary:
        details_parts.append(f"\n{assignment_summary}")

    description = "\n".join(details_parts)
    location = "온라인" if schedule["type"] == "online" else "오프라인"

    return build_gcal_url(
        title=title,
        start_date=schedule["date"],
        end_date=schedule.get("date_end"),
        description=description,
        location=location,
    )
