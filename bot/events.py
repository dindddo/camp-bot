from slack_bolt import App

from config import Config


def register_events(app: App):
    """Slack 이벤트 리스너를 등록합니다."""

    @app.event("app_mention")
    def handle_mention(event, say):
        """봇이 멘션되면 응답합니다."""
        user = event["user"]
        text = event.get("text", "")

        say(
            f"안녕하세요 <@{user}>! 👋\n"
            f"*{Config.CAMP_NAME}* 운영봇입니다.\n"
            f"`/camp-help`로 사용 가능한 명령어를 확인해주세요!"
        )

    @app.event("message")
    def handle_message(event, logger):
        """메시지 이벤트를 로깅합니다 (향후 확장용)."""
        pass
