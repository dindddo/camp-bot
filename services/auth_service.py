"""Google OAuth2 인증 서비스."""
from __future__ import annotations

import secrets
from urllib.parse import urlencode

import httpx

from config import Config
from models.database import Participant, SessionLocal
from services.usage_service import generate_token

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def get_google_login_url(state: str) -> str:
    """Google OAuth2 로그인 URL을 생성합니다."""
    params = {
        "client_id": Config.GOOGLE_CLIENT_ID,
        "redirect_uri": Config.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict | None:
    """Authorization code를 access token으로 교환합니다."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": Config.GOOGLE_CLIENT_ID,
                "client_secret": Config.GOOGLE_CLIENT_SECRET,
                "redirect_uri": Config.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if resp.status_code != 200:
            return None
        return resp.json()


async def get_google_user(access_token: str) -> dict | None:
    """Google 사용자 정보를 가져옵니다."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code != 200:
            return None
        return resp.json()


def login_or_register(google_user: dict) -> dict:
    """Google 사용자 정보로 로그인 또는 자동 등록합니다.

    Returns: {"participant": Participant, "token": str, "is_new": bool}
    """
    email = google_user.get("email", "")
    name = google_user.get("name", email.split("@")[0])
    picture = google_user.get("picture", "")

    db = SessionLocal()
    try:
        # 이메일로 기존 참가자 찾기
        participant = db.query(Participant).filter(Participant.email == email).first()

        if participant:
            token = generate_token(participant.id)
            return {
                "participant_id": participant.id,
                "name": participant.name,
                "email": participant.email,
                "picture": picture,
                "token": token,
                "is_new": False,
            }

        # 새 참가자 등록
        participant = Participant(
            slack_user_id=f"google_{secrets.token_hex(8)}",
            name=name,
            email=email,
            role="participant",
        )
        db.add(participant)
        db.commit()
        db.refresh(participant)

        token = generate_token(participant.id)
        return {
            "participant_id": participant.id,
            "name": participant.name,
            "email": participant.email,
            "picture": picture,
            "token": token,
            "is_new": True,
        }
    finally:
        db.close()
