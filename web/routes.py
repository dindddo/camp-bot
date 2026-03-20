from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from config import Config
from services.announce_service import get_announcements
from services.participant_service import (
    get_all_participants,
    get_dashboard_stats,
    get_submission_map,
    get_participant_rates,
)
from services.usage_service import (
    get_leaderboard,
    get_usage_summary,
    format_tokens,
    format_cost,
)
from web.auth import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="web/templates")


def _base_context(request: Request) -> dict:
    """모든 페이지에 공통으로 전달되는 컨텍스트."""
    return {
        "request": request,
        "camp_name": Config.CAMP_NAME,
        "user": get_current_user(request),
    }


@router.get("/")
async def dashboard(request: Request):
    """메인 대시보드 페이지."""
    from datetime import date as date_type
    today_str = date_type.today().strftime("%Y-%m-%d")

    announcements = get_announcements(limit=10)
    stats = get_dashboard_stats()
    leaderboard = get_leaderboard()
    leaderboard_daily = get_leaderboard(date_filter=today_str)
    usage_summary = get_usage_summary()
    usage_summary_daily = get_usage_summary(date_filter=today_str)

    ctx = _base_context(request)
    ctx.update({
        "camp_day": Config.camp_day(),
        "days_remaining": Config.days_remaining(),
        "progress": Config.progress_percent(),
        "start_date": Config.CAMP_START_DATE.strftime("%Y.%m.%d"),
        "end_date": Config.CAMP_END_DATE.strftime("%Y.%m.%d"),
        "announcements": announcements,
        "schedule": Config.get_schedule(),
        "today_schedule": Config.today_schedule(),
        "next_schedule": Config.next_schedule(),
        "stats": stats,
        "leaderboard": leaderboard,
        "leaderboard_daily": leaderboard_daily,
        "usage_summary": usage_summary,
        "usage_summary_daily": usage_summary_daily,
        "format_tokens": format_tokens,
        "format_cost": format_cost,
    })
    return templates.TemplateResponse("dashboard.html", ctx)


@router.get("/course")
async def course_page(request: Request):
    """코스 페이지."""
    ctx = _base_context(request)
    ctx.update({
        "schedule": Config.get_schedule(),
        "today_schedule": Config.today_schedule(),
        "camp_day": Config.camp_day(),
    })
    return templates.TemplateResponse("course.html", ctx)


@router.get("/announcements")
async def announcements_page(request: Request):
    """공지 이력 페이지."""
    ctx = _base_context(request)
    ctx["announcements"] = get_announcements(limit=50)
    return templates.TemplateResponse("announcements.html", ctx)
