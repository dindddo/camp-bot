import asyncio

from slack_bolt import App

from config import Config
from services.announce_service import get_announcements, send_announcement
from services.calendar_service import get_day_calendar_url
from services.claude_service import generate_announcement
from services.template_service import get_day_template, get_available_days, parse_day_number


def register_commands(app: App):
    """슬래시 커맨드를 등록합니다."""

    @app.command("/camp-announce")
    def handle_announce(ack, command, client, respond):
        """공지를 작성하고 발송합니다.

        사용법:
            /camp-announce 내일 오전 10시 세션 리마인더
            /camp-announce --channel #announcements 과제 마감 안내
        """
        ack()
        text = command["text"].strip()
        user_id = command["user_id"]

        if not text:
            available = get_available_days()
            days_list = ", ".join([f"`day{d}`" for d in available])
            respond(
                "사용법:\n"
                f"• `/camp-announce day1` — Day별 과제 공지 발송 (등록된 Day: {days_list})\n"
                "• `/camp-announce [자유 내용]` — AI가 공지문 작성 후 발송\n"
                "• `/camp-announce --channel #채널 [내용]` — 특정 채널에 발송"
            )
            return

        # 채널 파싱
        channel = Config.DEFAULT_CHANNEL
        if text.startswith("--channel"):
            parts = text.split(maxsplit=2)
            if len(parts) >= 3:
                channel = parts[1].strip("#")
                text = parts[2]

        # Day 템플릿 확인
        day_num = parse_day_number(text)
        if day_num is not None:
            template = get_day_template(day_num)
            if not template:
                available = get_available_days()
                days_list = ", ".join([f"`day{d}`" for d in available])
                respond(f"❌ Day {day_num} 템플릿이 아직 없습니다.\n등록된 Day: {days_list}")
                return

            # 템플릿 미리보기 → 확인 후 발송
            # 내용이 길면 앞부분만 미리보기
            preview = template[:500] + ("..." if len(template) > 500 else "")

            # Google Calendar 링크 생성
            gcal_url = get_day_calendar_url(day_num, assignment_summary=template[:200])

            action_elements = [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": f"✅ Day {day_num} 공지 발송"},
                    "style": "primary",
                    "action_id": "approve_announce",
                    "value": f"{channel}|||{day_num}|||{template}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ 취소"},
                    "action_id": "cancel_announce",
                },
            ]

            preview_blocks = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*📋 Day {day_num} 과제 공지 미리보기:*"},
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": preview},
                },
            ]

            if gcal_url:
                preview_blocks.append({
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"📅 공지 발송 시 *캘린더 추가 버튼*이 함께 포함됩니다"},
                    ],
                })

            preview_blocks.append({"type": "divider"})
            preview_blocks.append({"type": "actions", "elements": action_elements})

            respond(blocks=preview_blocks)
            return

        # AI 공지 작성 모드
        respond("🤖 AI가 공지문을 작성 중입니다...")

        content = asyncio.get_event_loop().run_until_complete(
            generate_announcement(text)
        )

        respond(
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*📝 공지 미리보기:*\n\n{content}"},
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ 발송"},
                            "style": "primary",
                            "action_id": "approve_announce",
                            "value": f"{channel}|||{content}",
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "❌ 취소"},
                            "action_id": "cancel_announce",
                        },
                    ],
                },
            ]
        )

    @app.action("approve_announce")
    def handle_approve(ack, action, client, respond):
        """공지 발송을 승인합니다."""
        ack()
        value = action["value"]
        parts = value.split("|||")

        # day_num이 포함된 경우: channel|||day_num|||content
        # 포함되지 않은 경우 (AI 공지): channel|||content
        if len(parts) == 3:
            channel, day_num_str, content = parts
            day_num = int(day_num_str) if day_num_str.isdigit() else None
        else:
            channel, content = parts[0], parts[-1]
            day_num = None

        # 제목 추출 (첫 줄)
        lines = content.strip().split("\n")
        title = lines[0].strip("# ").strip("*").strip()[:100]

        # Google Calendar 링크 생성
        gcal_url = None
        if day_num:
            gcal_url = get_day_calendar_url(day_num, assignment_summary=content[:200])

        announcement = send_announcement(
            slack_client=client,
            title=title,
            content=content,
            channel=channel,
            gcal_url=gcal_url,
        )
        respond(f"✅ 공지가 #{channel}에 발송되었습니다! (ID: {announcement.id})")

    @app.action("cancel_announce")
    def handle_cancel(ack, respond):
        """공지 발송을 취소합니다."""
        ack()
        respond("❌ 공지 발송이 취소되었습니다.")

    @app.action("open_gcal")
    def handle_gcal_click(ack):
        """Google Calendar 버튼 클릭을 처리합니다 (URL 버튼이므로 ack만)."""
        ack()

    @app.command("/camp-status")
    def handle_status(ack, command, respond):
        """캠프 현황을 보여줍니다."""
        ack()

        announcements = get_announcements(limit=5)
        recent = "\n".join(
            [f"• {a.title} ({a.sent_at.strftime('%m/%d') if a.sent_at else '예약'})"
             for a in announcements]
        ) or "아직 공지가 없습니다."

        progress = Config.progress_percent()
        bar_filled = int(progress / 10)
        bar_empty = 10 - bar_filled
        progress_bar = "█" * bar_filled + "░" * bar_empty

        # 오늘/다음 일정
        today = Config.today_schedule()
        next_up = Config.next_schedule()
        schedule_text = ""
        if today:
            schedule_text = f"📍 *오늘: Day {today['day']}* — {today['title']}"
            if today.get("deliverable"):
                schedule_text += f"\n📝 _{today['deliverable']}_"
        elif next_up:
            schedule_text = f"⏭️ *다음: Day {next_up['day']}* ({next_up['date']}) — {next_up['title']}"
        else:
            schedule_text = "캠프가 종료되었습니다 🎉"

        # 전체 일정 요약
        schedule_list = "\n".join(
            f"{'✅' if Config.camp_day() > s['day'] else '📍' if today and today['day'] == s['day'] else '⬜'} "
            f"Day {s['day']} ({s['date']}) — {s['title']}"
            for s in Config.get_schedule()
        )

        respond(
            blocks=[
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"📊 {Config.CAMP_NAME} 현황"},
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*📅 현재*\nDay {Config.camp_day() or '-'}"},
                        {"type": "mrkdwn", "text": f"*⏳ 종료까지*\nD-{Config.days_remaining()}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*진행률*\n{progress_bar} {progress:.0f}%"},
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": schedule_text},
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*📅 전체 일정*\n{schedule_list}"},
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*📢 최근 공지*\n{recent}"},
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": "🌐 대시보드에서 더 자세히 보기"},
                    ],
                },
            ]
        )

    @app.command("/camp-help")
    def handle_help(ack, respond):
        """사용 가능한 명령어를 보여줍니다."""
        ack()
        respond(
            blocks=[
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "🤖 Camp Bot 명령어"},
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "*📋 Day별 과제 공지*\n"
                            "• `/camp-announce day1` — Day 1 과제 공지 발송\n"
                            "• `/camp-announce day2` — Day 2 과제 공지 발송\n"
                            "• `/camp-announce day3` — Day 3 과제 공지 발송\n\n"
                            "*✍️ AI 공지 작성*\n"
                            "• `/camp-announce [내용]` — AI가 공지문 작성 후 발송\n"
                            "• `/camp-announce --channel #채널 [내용]` — 특정 채널에 발송\n\n"
                            "*📊 현황*\n"
                            "• `/camp-status` — 캠프 현황 조회\n\n"
                            "*❓ 도움*\n"
                            "• `/camp-help` — 이 도움말 보기"
                        ),
                    },
                },
            ]
        )
