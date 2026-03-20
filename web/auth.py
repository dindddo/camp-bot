"""Google OAuth2 인증 라우트."""
from __future__ import annotations

import secrets
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from itsdangerous import URLSafeSerializer

from config import Config
from services.auth_service import (
    get_google_login_url,
    exchange_code,
    get_google_user,
    login_or_register,
)

auth_router = APIRouter(prefix="/auth")
signer = URLSafeSerializer(Config.SESSION_SECRET)


def get_current_user(request: Request) -> dict | None:
    """쿠키에서 현재 로그인된 사용자를 가져옵니다."""
    session = request.cookies.get("session")
    if not session:
        return None
    try:
        return signer.loads(session)
    except Exception:
        return None


@auth_router.get("/login")
async def login(request: Request):
    """Google 로그인 페이지로 리다이렉트합니다."""
    if not Config.GOOGLE_CLIENT_ID:
        return HTMLResponse(
            "<h3>Google OAuth2가 설정되지 않았습니다.</h3>"
            "<p>.env에 GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET을 설정해주세요.</p>",
            status_code=500,
        )
    state = secrets.token_hex(16)
    url = get_google_login_url(state)
    response = RedirectResponse(url)
    response.set_cookie("oauth_state", state, httponly=True, max_age=600)
    return response


@auth_router.get("/callback")
async def callback(request: Request, code: str = "", error: str = ""):
    """Google OAuth2 콜백을 처리합니다."""
    if error:
        return RedirectResponse("/?error=auth_denied")

    if not code:
        return RedirectResponse("/?error=no_code")

    # Code → Token
    token_data = await exchange_code(code)
    if not token_data:
        return RedirectResponse("/?error=token_exchange_failed")

    # Token → User Info
    google_user = await get_google_user(token_data["access_token"])
    if not google_user:
        return RedirectResponse("/?error=userinfo_failed")

    # Login or Register
    result = login_or_register(google_user)

    # 세션 쿠키 설정
    session_data = signer.dumps({
        "participant_id": result["participant_id"],
        "name": result["name"],
        "email": result["email"],
        "picture": result.get("picture", ""),
        "token": result["token"],
    })

    response = RedirectResponse("/")
    response.set_cookie(
        "session",
        session_data,
        httponly=True,
        max_age=60 * 60 * 24 * 14,  # 14일
        samesite="lax",
    )
    response.delete_cookie("oauth_state")
    return response


@auth_router.get("/logout")
async def logout():
    """로그아웃합니다."""
    response = RedirectResponse("/")
    response.delete_cookie("session")
    return response
