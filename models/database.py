from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from config import Config

engine = create_engine(Config.DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    channel = Column(String(100), default=Config.DEFAULT_CHANNEL)
    scheduled_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    is_sent = Column(Boolean, default=False)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    slack_ts = Column(String(50), nullable=True)


class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True)
    slack_user_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(200), nullable=True)
    team = Column(String(100), nullable=True)
    role = Column(String(50), default="participant")  # participant, mentor, admin
    is_active = Column(Boolean, default=True)
    joined_at = Column(DateTime, default=datetime.utcnow)


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True)
    participant_id = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)  # Day 1~5
    status = Column(String(20), default="submitted")  # submitted, reviewed, late
    submitted_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)


class UserToken(Base):
    """참가자 인증 토큰."""
    __tablename__ = "user_tokens"

    id = Column(Integer, primary_key=True)
    token = Column(String(100), unique=True, nullable=False)
    participant_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Usage(Base):
    """Claude Code 사용량 기록."""
    __tablename__ = "usage"

    id = Column(Integer, primary_key=True)
    participant_id = Column(Integer, nullable=False)
    session_id = Column(String(200), nullable=True)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD (KST)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cache_creation_tokens = Column(Integer, default=0)
    cache_read_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Integer, default=0)  # cents (소수점 방지)
    models_used = Column(Text, nullable=True)  # JSON array string
    created_at = Column(DateTime, default=datetime.utcnow)


class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"

    id = Column(Integer, primary_key=True)
    post_type = Column(String(50), nullable=False)  # daily_reminder, weekly_report
    channel = Column(String(100), default=Config.DEFAULT_CHANNEL)
    cron_expression = Column(String(50), nullable=False)
    template = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(engine)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
