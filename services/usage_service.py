"""Claude Code 사용량 추적 서비스."""
from __future__ import annotations

import json
import secrets
from collections import defaultdict

from sqlalchemy import func

from config import Config
from models.database import Participant, Usage, UserToken, SessionLocal


def generate_token(participant_id: int) -> str:
    """참가자용 고유 토큰을 생성합니다."""
    token = f"sentbe_{secrets.token_hex(24)}"
    db = SessionLocal()
    try:
        existing = db.query(UserToken).filter(UserToken.participant_id == participant_id).first()
        if existing:
            return existing.token
        ut = UserToken(token=token, participant_id=participant_id)
        db.add(ut)
        db.commit()
        return token
    finally:
        db.close()


def auto_register(name: str, team: str = "") -> dict:
    """이름으로 자동 등록하고 토큰을 발급합니다."""
    db = SessionLocal()
    try:
        # 같은 이름이 이미 있으면 기존 토큰 반환
        existing = db.query(Participant).filter(Participant.name == name).first()
        if existing:
            token = generate_token(existing.id)
            return {"token": token, "name": existing.name, "is_new": False}

        # 새 참가자 등록
        participant = Participant(
            slack_user_id=f"auto_{secrets.token_hex(8)}",
            name=name,
            team=team or None,
            role="participant",
        )
        db.add(participant)
        db.commit()
        db.refresh(participant)

        token = generate_token(participant.id)
        return {"token": token, "name": participant.name, "is_new": True}
    finally:
        db.close()


def get_participant_by_token(token: str) -> Participant | None:
    """토큰으로 참가자를 조회합니다."""
    db = SessionLocal()
    try:
        ut = db.query(UserToken).filter(UserToken.token == token).first()
        if not ut:
            return None
        return db.query(Participant).filter(Participant.id == ut.participant_id).first()
    finally:
        db.close()


def submit_usage(participant_id: int, data: dict) -> bool:
    """사용량 데이터를 저장합니다. session_id 기반 중복 방지."""
    db = SessionLocal()
    try:
        session_id = data.get("session_id")
        if session_id:
            existing = (
                db.query(Usage)
                .filter(Usage.participant_id == participant_id, Usage.session_id == session_id)
                .first()
            )
            if existing:
                return False  # 중복

        usage = Usage(
            participant_id=participant_id,
            session_id=session_id,
            date=data.get("date", ""),
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            cache_creation_tokens=data.get("cache_creation_tokens", 0),
            cache_read_tokens=data.get("cache_read_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
            total_cost=int(data.get("total_cost", 0) * 100),  # dollars → cents
            models_used=json.dumps(data.get("models_used", [])),
        )
        db.add(usage)
        db.commit()
        return True
    finally:
        db.close()


def get_leaderboard(date_filter: str | None = None) -> list[dict]:
    """리더보드 데이터를 반환합니다.

    Args:
        date_filter: 특정 날짜만 (YYYY-MM-DD). None이면 전체 누적.
    """
    db = SessionLocal()
    try:
        query = db.query(
            Usage.participant_id,
            func.sum(Usage.total_tokens).label("total_tokens"),
            func.sum(Usage.input_tokens + Usage.output_tokens).label("io_tokens"),
            func.sum(Usage.cache_read_tokens).label("cache_tokens"),
            func.sum(Usage.total_cost).label("total_cost"),
        ).group_by(Usage.participant_id)

        if date_filter:
            query = query.filter(Usage.date == date_filter)

        results = query.order_by(func.sum(Usage.total_tokens).desc()).all()

        # 참가자 정보 매핑
        participants = {p.id: p for p in db.query(Participant).all()}

        # Usage가 있는 참가자 ID 수집
        seen_ids = set()

        leaderboard = []
        for row in results:
            p = participants.get(row.participant_id)
            if not p:
                continue
            seen_ids.add(row.participant_id)
            total = row.total_tokens or 0
            leaderboard.append({
                "rank": 0,  # 아래에서 채움
                "participant_id": row.participant_id,
                "name": p.name,
                "team": p.team or "",
                "role": p.role,
                "total_tokens": total,
                "io_tokens": row.io_tokens or 0,
                "cache_tokens": row.cache_tokens or 0,
                "total_cost": (row.total_cost or 0) / 100,  # cents → dollars
                "level": _get_level(total),
            })

        # Usage가 없는 참가자도 누적 리더보드에 표시
        if not date_filter:
            for p in participants.values():
                if p.id not in seen_ids and p.role == "participant":
                    leaderboard.append({
                        "rank": 0,
                        "participant_id": p.id,
                        "name": p.name,
                        "team": p.team or "",
                        "role": p.role,
                        "total_tokens": 0,
                        "io_tokens": 0,
                        "cache_tokens": 0,
                        "total_cost": 0,
                        "level": _get_level(0),
                    })

        for i, entry in enumerate(leaderboard):
            entry["rank"] = i + 1

        return leaderboard
    finally:
        db.close()


def get_usage_summary(date_filter: str | None = None) -> dict:
    """전체 사용량 요약을 반환합니다."""
    db = SessionLocal()
    try:
        query = db.query(
            func.count(func.distinct(Usage.participant_id)).label("active_users"),
            func.sum(Usage.total_tokens).label("total_tokens"),
            func.sum(Usage.total_cost).label("total_cost"),
        )
        if date_filter:
            query = query.filter(Usage.date == date_filter)

        row = query.first()
        return {
            "active_users": row.active_users or 0,
            "total_tokens": row.total_tokens or 0,
            "total_cost": (row.total_cost or 0) / 100,
        }
    finally:
        db.close()


def _get_level(total_tokens: int) -> dict:
    """토큰 사용량 기반 레벨을 반환합니다. (해리포터 테마)"""
    levels = [
        (200_000_000, "🧙‍♂️", "덤블도어"),
        (50_000_000, "⚡", "불사조 기사단"),
        (10_000_000, "🦁", "그리핀도르"),
        (1_000_000, "🧹", "호그와트 입학"),
    ]
    for threshold, emoji, label in levels:
        if total_tokens >= threshold:
            return {"emoji": emoji, "label": label}
    return {"emoji": "✉️", "label": "입학 편지"}


def format_tokens(n: int) -> str:
    """토큰 수를 읽기 쉽게 포맷합니다."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def format_cost(c: float) -> str:
    """비용을 포맷합니다."""
    if c >= 1:
        return f"${c:,.0f}"
    return f"${c:.1f}"
