from __future__ import annotations

from collections import defaultdict

from models.database import Participant, Submission, SessionLocal
from config import Config


def get_all_participants(active_only: bool = True) -> list[Participant]:
    db = SessionLocal()
    try:
        q = db.query(Participant)
        if active_only:
            q = q.filter(Participant.is_active == True)
        return q.order_by(Participant.name).all()
    finally:
        db.close()


def get_participant_count() -> dict:
    db = SessionLocal()
    try:
        total = db.query(Participant).filter(Participant.is_active == True).count()
        mentors = (
            db.query(Participant)
            .filter(Participant.is_active == True, Participant.role == "mentor")
            .count()
        )
        return {"total": total, "participants": total - mentors, "mentors": mentors}
    finally:
        db.close()


def get_submissions_by_day() -> dict[int, dict]:
    """Day별 제출 현황을 반환합니다."""
    db = SessionLocal()
    try:
        total_participants = (
            db.query(Participant)
            .filter(Participant.is_active == True, Participant.role == "participant")
            .count()
        )
        submissions = db.query(Submission).all()

        result = {}
        for day_info in Config.get_schedule():
            day = day_info["day"]
            day_subs = [s for s in submissions if s.day == day]
            submitted = len(day_subs)
            reviewed = len([s for s in day_subs if s.status == "reviewed"])
            late = len([s for s in day_subs if s.status == "late"])
            rate = (submitted / total_participants * 100) if total_participants > 0 else 0
            result[day] = {
                "submitted": submitted,
                "reviewed": reviewed,
                "late": late,
                "total": total_participants,
                "rate": round(rate, 1),
            }
        return result
    finally:
        db.close()


def get_submission_map() -> dict[int, dict[int, str]]:
    """참가자별 Day별 제출 상태를 반환합니다.

    Returns: {participant_id: {day: status}}
    """
    db = SessionLocal()
    try:
        submissions = db.query(Submission).all()
        result = defaultdict(dict)
        for s in submissions:
            result[s.participant_id][s.day] = s.status
        return dict(result)
    finally:
        db.close()


def get_participant_rates() -> dict[int, float]:
    """참가자별 제출률을 반환합니다.

    Returns: {participant_id: rate}
    """
    current_day = Config.camp_day()
    if current_day <= 0:
        return {}

    sub_map = get_submission_map()
    active_days = [d for d in range(1, current_day + 1)]
    total_days = len(active_days)
    if total_days == 0:
        return {}

    result = {}
    db = SessionLocal()
    try:
        participants = (
            db.query(Participant)
            .filter(Participant.is_active == True, Participant.role == "participant")
            .all()
        )
        for p in participants:
            submitted = sum(1 for d in active_days if d in sub_map.get(p.id, {}))
            result[p.id] = round(submitted / total_days * 100, 0)
        return result
    finally:
        db.close()


def get_dashboard_stats() -> dict:
    """대시보드용 통합 통계를 반환합니다."""
    counts = get_participant_count()
    submissions = get_submissions_by_day()
    total_submitted = sum(d["submitted"] for d in submissions.values())

    # 현재 Day까지의 평균 제출률
    current_day = Config.camp_day()
    active_days = [d for d in submissions if d <= current_day and d > 0]
    avg_rate = 0.0
    if active_days:
        avg_rate = sum(submissions[d]["rate"] for d in active_days) / len(active_days)

    return {
        "participants": counts,
        "submissions_by_day": submissions,
        "total_submissions": total_submitted,
        "avg_submission_rate": round(avg_rate, 1),
    }
