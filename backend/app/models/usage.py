import uuid
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.constants import AI_OPERATIONS, sql_in
from app.models.mixins import CreatedAt, UUIDPk


class AIUsage(UUIDPk, CreatedAt, Base):
    """Учёт AI-вызовов для расчёта себестоимости. Текстов диалогов здесь нет.
    При удалении пользователя ссылки обнуляются, суммы остаются."""

    __tablename__ = "ai_usage"
    __table_args__ = (
        CheckConstraint(f"operation IN {sql_in(AI_OPERATIONS)}", name="operation"),
        Index("ix_ai_usage_created_at", "created_at"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training_sessions.id", ondelete="SET NULL"), index=True
    )
    operation: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_cached: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("0"))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
