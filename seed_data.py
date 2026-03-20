"""샘플 데이터를 생성합니다. 개발/데모용."""
from datetime import datetime, timedelta
import random

from models.database import init_db, SessionLocal, Participant, Submission, Announcement, UserToken, Usage

SAMPLE_PARTICIPANTS = [
    {"name": "김민수", "team": "A팀", "role": "participant"},
    {"name": "이서연", "team": "A팀", "role": "participant"},
    {"name": "박지훈", "team": "A팀", "role": "participant"},
    {"name": "최예진", "team": "B팀", "role": "participant"},
    {"name": "정도현", "team": "B팀", "role": "participant"},
    {"name": "한소영", "team": "B팀", "role": "participant"},
    {"name": "오태윤", "team": "C팀", "role": "participant"},
    {"name": "송하린", "team": "C팀", "role": "participant"},
    {"name": "윤재혁", "team": "C팀", "role": "participant"},
    {"name": "임수빈", "team": "C팀", "role": "participant"},
    {"name": "강현우", "team": "D팀", "role": "participant"},
    {"name": "배지민", "team": "D팀", "role": "participant"},
    {"name": "조은서", "team": "D팀", "role": "participant"},
    {"name": "황민지", "team": "D팀", "role": "participant"},
    {"name": "류성진", "team": "D팀", "role": "participant"},
    {"name": "김태희", "team": None, "role": "mentor"},
    {"name": "이준호", "team": None, "role": "mentor"},
]

SAMPLE_ANNOUNCEMENTS = [
    {
        "title": "AI Native Camp 시작을 환영합니다!",
        "content": "안녕하세요! Sentbe AI Native Camp에 오신 것을 환영합니다.\n\nDay 1 온라인 OT + 핸즈온 실습이 시작되었습니다.\n주말 동안 자율적으로 ~4시간 분량의 실습을 진행해주세요.",
        "sent_at": datetime(2026, 3, 14, 10, 0),
    },
    {
        "title": "Day 1 핸즈온 실습 리마인더",
        "content": "Day 1 핸즈온 실습 마감이 3/22(일)까지입니다.\n아직 시작하지 않으신 분들은 서둘러주세요!",
        "sent_at": datetime(2026, 3, 19, 9, 0),
    },
    {
        "title": "Day 2 학습 + 과제 안내",
        "content": "Day 2가 시작되었습니다!\n오늘의 학습 내용을 확인하고 과제를 제출해주세요.\n마감: 오늘 23:59",
        "sent_at": datetime(2026, 3, 23, 9, 0),
    },
    {
        "title": "Day 3 학습 + 과제 안내",
        "content": "Day 3가 시작되었습니다!\n오늘의 학습 내용을 확인하고 과제를 제출해주세요.\n마감: 오늘 23:59",
        "sent_at": datetime(2026, 3, 24, 9, 0),
    },
    {
        "title": "Day 4 학습 + 과제 안내",
        "content": "Day 4가 시작되었습니다!\n오늘의 학습 내용을 확인하고 과제를 제출해주세요.\n마감: 오늘 23:59",
        "sent_at": datetime(2026, 3, 25, 9, 0),
    },
]


def seed():
    init_db()
    db = SessionLocal()

    # 기존 데이터 확인
    if db.query(Participant).count() > 0:
        print("이미 샘플 데이터가 있습니다. 스킵합니다.")
        db.close()
        return

    try:
        # 참가자 추가
        participants = []
        for i, p in enumerate(SAMPLE_PARTICIPANTS):
            participant = Participant(
                slack_user_id=f"U{i+1:04d}SAMPLE",
                name=p["name"],
                team=p["team"],
                role=p["role"],
                joined_at=datetime(2026, 3, 14, 9, 0),
            )
            db.add(participant)
            db.flush()
            participants.append(participant)

        # 과제 제출 (Day 1~3은 완료, Day 4는 진행 중)
        only_participants = [p for p in participants if p.role == "participant"]

        for day in range(1, 5):
            if day <= 3:
                # Day 1~3: 대부분 제출
                submitters = random.sample(
                    only_participants,
                    k=random.randint(len(only_participants) - 2, len(only_participants)),
                )
            else:
                # Day 4: 일부만 제출 (진행 중)
                submitters = random.sample(
                    only_participants,
                    k=random.randint(3, len(only_participants) // 2),
                )

            base_date = datetime(2026, 3, [22, 23, 24, 25][day - 1])
            for p in submitters:
                hour = random.randint(10, 22)
                status = "reviewed" if day <= 2 else "submitted"
                if day <= 3 and random.random() < 0.1:
                    status = "late"
                sub = Submission(
                    participant_id=p.id,
                    day=day,
                    status=status,
                    submitted_at=base_date.replace(hour=hour, minute=random.randint(0, 59)),
                    reviewed_at=base_date.replace(hour=23) if status == "reviewed" else None,
                )
                db.add(sub)

        # 공지 추가
        for a in SAMPLE_ANNOUNCEMENTS:
            ann = Announcement(
                title=a["title"],
                content=a["content"],
                channel="general",
                is_sent=True,
                sent_at=a["sent_at"],
                created_at=a["sent_at"],
            )
            db.add(ann)

        # 토큰 생성 + 사용량 데이터
        import secrets
        for p in only_participants:
            token = f"sentbe_{secrets.token_hex(24)}"
            db.add(UserToken(token=token, participant_id=p.id))

            # 각 참가자에게 랜덤 사용량 부여 (여러 세션)
            for day_offset in range(7):  # 3/14 ~ 3/20
                if random.random() < 0.3:
                    continue  # 30% 확률로 그날은 안씀
                session_date = datetime(2026, 3, 14 + day_offset)
                date_str = session_date.strftime("%Y-%m-%d")
                num_sessions = random.randint(1, 4)
                for s in range(num_sessions):
                    inp = random.randint(50_000, 2_000_000)
                    out = random.randint(5_000, 200_000)
                    cw = random.randint(10_000, 500_000)
                    cr = random.randint(100_000, 5_000_000)
                    total = inp + out + cw + cr
                    cost = (inp * 3 + out * 15 + cw * 3.75 + cr * 0.30) / 1_000_000
                    db.add(Usage(
                        participant_id=p.id,
                        session_id=f"sess_{p.id}_{day_offset}_{s}",
                        date=date_str,
                        input_tokens=inp,
                        output_tokens=out,
                        cache_creation_tokens=cw,
                        cache_read_tokens=cr,
                        total_tokens=total,
                        total_cost=int(cost * 100),
                        models_used='["claude-sonnet-4-6"]',
                    ))

        db.commit()
        print(f"✅ 샘플 데이터 생성 완료!")
        print(f"   참가자: {len(participants)}명 (멘토 포함)")
        print(f"   공지: {len(SAMPLE_ANNOUNCEMENTS)}건")
        print(f"   사용량: 토큰 + 비용 데이터 생성됨")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
