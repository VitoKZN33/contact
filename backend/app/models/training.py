import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.constants import (
    ANALYSIS_STATUSES,
    DIFFICULTIES,
    GENDERS,
    INTERACTION_MODES,
    MESSAGE_ROLES,
    MESSAGE_STATUSES,
    PERSONAS,
    TRAINING_STATUSES,
    sql_in,
)
from app.models.mixins import CreatedAt, UUIDPk


class TrainingSession(UUIDPk, Base):
    __tablename__ = "training_sessions"
    __table_args__ = (
        CheckConstraint(f"status IN {sql_in(TRAINING_STATUSES)}", name="status"),
        CheckConstraint(f"analysis_status IN {sql_in(ANALYSIS_STATUSES)}", name="analysis_status"),
        CheckConstraint(f"persona_type IN {sql_in(PERSONAS)}", name="persona_type"),
        CheckConstraint(f"persona_gender IN {sql_in(GENDERS)}", name="persona_gender"),
        CheckConstraint(f"difficulty IN {sql_in(DIFFICULTIES)}", name="difficulty"),
        CheckConstraint(f"interaction_mode IN {sql_in(INTERACTION_MODES)}", name="interaction_mode"),
        UniqueConstraint("user_id", "idempotency_key", name="uq_training_sessions_user_idempotency"),
        # Одна активная тренировка на пользователя — основа кнопки «Продолжить»
        Index("uq_training_sessions_active_user", "user_id", unique=True, postgresql_where=text("status = 'active'")),
        Index("ix_training_sessions_user_completed", "user_id", "completed_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Версии сценариев не удаляются, поэтому RESTRICT
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenarios.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    custom_situation: Mapped[str | None] = mapped_column(Text)
    persona_type: Mapped[str] = mapped_column(String(32), nullable=False)
    persona_gender: Mapped[str] = mapped_column(String(16), nullable=False)
    persona_name: Mapped[str] = mapped_column(String(64), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False)
    interaction_mode: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'text'"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'active'"))
    analysis_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'none'"))
    context_summary: Mapped[str | None] = mapped_column(Text)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(UUIDPk, CreatedAt, Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(f"role IN {sql_in(MESSAGE_ROLES)}", name="role"),
        CheckConstraint(f"status IN {sql_in(MESSAGE_STATUSES)}", name="status"),
        CheckConstraint(f"input_mode IN {sql_in(INTERACTION_MODES)}", name="input_mode"),
        UniqueConstraint("session_id", "sequence_number", name="uq_messages_session_sequence"),
        UniqueConstraint("session_id", "client_message_id", name="uq_messages_session_client_id"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training_sessions.id", ondelete="CASCADE"), nullable=False
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    input_mode: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'text'"))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    client_message_id: Mapped[str | None] = mapped_column(String(64))


class TrainingResult(UUIDPk, CreatedAt, Base):
    __tablename__ = "training_results"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training_sessions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    strengths: Mapped[list] = mapped_column(JSONB, nullable=False)
    improvement_points: Mapped[list] = mapped_column(JSONB, nullable=False)
    alternative_replies: Mapped[list] = mapped_column(JSONB, nullable=False)
    scores: Mapped[list] = mapped_column(JSONB, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
