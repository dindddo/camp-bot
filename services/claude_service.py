import anthropic

from config import Config

client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)

SYSTEM_PROMPT = f"""당신은 {Config.CAMP_NAME}의 운영 어시스턴트입니다.
캠프 참가자들에게 보내는 공지, 리마인더, 안내 메시지를 작성합니다.

작성 원칙:
- 친근하고 전문적인 톤
- 핵심 정보를 먼저, 부가 설명은 뒤에
- Slack에서 읽기 좋도록 짧고 명확하게
- 이모지를 적절히 활용하여 가독성 향상
- 한국어로 작성
"""


async def generate_announcement(prompt: str) -> str:
    """AI로 공지문을 생성합니다."""
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"다음 내용으로 Slack 공지문을 작성해주세요:\n\n{prompt}",
            }
        ],
    )
    return message.content[0].text


async def generate_summary(data: dict) -> str:
    """캠프 현황 요약을 생성합니다."""
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"다음 캠프 데이터를 간결하게 요약해주세요:\n\n{data}",
            }
        ],
    )
    return message.content[0].text
