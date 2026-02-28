"""SQLAlchemy ORM models -- PostgreSQL schema definition."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text,
    SmallInteger, ForeignKey, Float, BigInteger,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import DeclarativeBase, relationship


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class UserModel(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_new_uuid)
    full_name = Column(String(100), nullable=False)
    username = Column(String(30), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    whatsapp = Column(String(20), nullable=False)
    profession = Column(String(30), nullable=False)
    password_hash = Column(String(255), nullable=False)
    salt = Column(String(64), nullable=False, default="")
    hash_algorithm = Column(String(10), nullable=False, default="bcrypt")
    # email_verified defaults TRUE so existing users are never locked out.
    # New registrations are created with email_verified=False via the repo.
    email_verified = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    sessions = relationship("GameSessionModel", back_populates="user", lazy="select")
    metrics = relationship("UserMetricsModel", back_populates="user", uselist=False, lazy="select")
    email_verifications = relationship("EmailVerificationModel", back_populates="user", lazy="select")


# ---------------------------------------------------------------------------
# Email Verification OTP tokens
# ---------------------------------------------------------------------------

class EmailVerificationModel(Base):
    __tablename__ = "email_verifications"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_new_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)
    # SHA-256 hex digest of the 6-digit code (never store plaintext)
    token_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    # NULL means not yet used; set to the timestamp when consumed
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    user = relationship("UserModel", back_populates="email_verifications")


# ---------------------------------------------------------------------------
# Characters (cosmetic only)
# ---------------------------------------------------------------------------

class CharacterModel(Base):
    __tablename__ = "characters"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_new_uuid)
    gender = Column(String(10), nullable=False)
    ethnicity = Column(String(10), nullable=False)
    avatar_index = Column(SmallInteger, nullable=False)


# ---------------------------------------------------------------------------
# Game Sessions (Player aggregate root)
# ---------------------------------------------------------------------------

class GameSessionModel(Base):
    __tablename__ = "game_sessions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_new_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True, index=True)
    name = Column(String(50), nullable=False)
    character_id = Column(UUID(as_uuid=False), ForeignKey("characters.id"), nullable=False)
    language = Column(String(10), nullable=False)
    stage = Column(String(20), nullable=False, default="Intern")
    score = Column(Integer, nullable=False, default=0)
    current_errors = Column(Integer, nullable=False, default=0)
    completed_challenges = Column(ARRAY(String), nullable=False, default=list)
    game_over_count = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="in_progress")
    # World state persistence
    collected_books = Column(ARRAY(String), nullable=False, default=list)
    completed_regions = Column(ARRAY(String), nullable=False, default=list)
    current_region = Column(String(50), nullable=True)
    player_world_x = Column(Integer, nullable=False, default=100)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    user = relationship("UserModel", back_populates="sessions")
    character = relationship("CharacterModel", lazy="joined")
    attempts = relationship(
        "AttemptModel",
        back_populates="session",
        order_by="AttemptModel.timestamp",
        lazy="select",
    )


# ---------------------------------------------------------------------------
# Attempts (immutable event record)
# ---------------------------------------------------------------------------

class AttemptModel(Base):
    __tablename__ = "attempts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_new_uuid)
    session_id = Column(UUID(as_uuid=False), ForeignKey("game_sessions.id"), nullable=False, index=True)
    challenge_id = Column(String(50), nullable=False)
    selected_index = Column(SmallInteger, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    points_awarded = Column(Integer, nullable=False, default=0)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    session = relationship("GameSessionModel", back_populates="attempts")


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

class LeaderboardEntryModel(Base):
    __tablename__ = "leaderboard_entries"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(UUID(as_uuid=False), nullable=True)
    player_name = Column(String(50), nullable=False)
    score = Column(Integer, nullable=False, index=True)
    stage = Column(String(20), nullable=False)
    language = Column(String(10), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=_utcnow)


# ---------------------------------------------------------------------------
# Challenges (seeded from JSON)
# ---------------------------------------------------------------------------

class ChallengeModel(Base):
    __tablename__ = "challenges"

    id = Column(String(50), primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    context_code = Column(Text, nullable=True)
    category = Column(String(30), nullable=False)
    required_stage = Column(String(20), nullable=False)
    region = Column(String(50), nullable=False)
    options = Column(JSONB, nullable=False)
    mentor = Column(String(50), nullable=True)
    points_on_correct = Column(Integer, nullable=False, default=100)


# ---------------------------------------------------------------------------
# User Metrics (aggregate statistics per user)
# ---------------------------------------------------------------------------

class UserMetricsModel(Base):
    __tablename__ = "user_metrics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), unique=True, nullable=False, index=True)
    total_games_started = Column(Integer, nullable=False, default=0)
    total_games_completed = Column(Integer, nullable=False, default=0)
    total_game_overs = Column(Integer, nullable=False, default=0)
    total_attempts = Column(Integer, nullable=False, default=0)
    total_correct = Column(Integer, nullable=False, default=0)
    total_wrong = Column(Integer, nullable=False, default=0)
    total_score_earned = Column(Integer, nullable=False, default=0)
    highest_score = Column(Integer, nullable=False, default=0)
    highest_stage = Column(String(20), nullable=False, default="Intern")
    accuracy_rate = Column(Float, nullable=False, default=0.0)
    favorite_language = Column(String(10), nullable=True)
    last_played_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    user = relationship("UserModel", back_populates="metrics")


# ---------------------------------------------------------------------------
# Game Events (immutable audit trail -- event sourcing)
# ---------------------------------------------------------------------------

class GameEventModel(Base):
    __tablename__ = "game_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=False), nullable=True, index=True)
    session_id = Column(UUID(as_uuid=False), nullable=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    payload = Column(JSONB, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=_utcnow, index=True)
