import threading

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from config import Config
from models.database import init_db
from bot.commands import register_commands
from bot.events import register_events
from web.routes import router as web_router
from web.api import api_router
from web.auth import auth_router
from services.scheduler_service import start_scheduler, stop_scheduler

# ──────────────────────────────────────
# Database
# ──────────────────────────────────────
init_db()

# ──────────────────────────────────────
# Slack Bot
# ──────────────────────────────────────
slack_app = App(token=Config.SLACK_BOT_TOKEN)
register_commands(slack_app)
register_events(slack_app)

# ──────────────────────────────────────
# FastAPI Dashboard
# ──────────────────────────────────────
web_app = FastAPI(title=f"{Config.CAMP_NAME} Dashboard")
web_app.mount("/static", StaticFiles(directory="web/static"), name="static")
web_app.include_router(auth_router)
web_app.include_router(web_router)
web_app.include_router(api_router)

# ──────────────────────────────────────
# Startup
# ──────────────────────────────────────


def run_slack_bot():
    """Socket Mode로 Slack 봇을 실행합니다."""
    handler = SocketModeHandler(slack_app, Config.SLACK_APP_TOKEN)
    handler.start()


def main():
    print(f"🚀 {Config.CAMP_NAME} Bot 시작!")
    print(f"📊 대시보드: http://localhost:8000")
    print(f"📅 캠프 Day {Config.camp_day()} | D-{Config.days_remaining()}")
    print()

    # 스케줄러 시작
    start_scheduler(slack_app.client)

    # Slack 봇을 별도 스레드에서 실행
    bot_thread = threading.Thread(target=run_slack_bot, daemon=True)
    bot_thread.start()

    # FastAPI 대시보드 (메인 스레드)
    import os
    port = int(os.getenv("PORT", 8000))
    try:
        uvicorn.run(web_app, host="0.0.0.0", port=port)
    finally:
        stop_scheduler()


if __name__ == "__main__":
    main()
