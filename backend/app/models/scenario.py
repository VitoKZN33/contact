from sqlalchemy import Boolean, CheckConstraint, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.constants import CATEGORIES, sql_in
from app.models.mixins import Timestamps, UUIDPk


class Scenario(UUIDPk, Timestamps, Base):
    """Версия сценария. Изменение = новая строка с version+1; старые версии
    остаются, чтобы прошлые тренировки и разборы ссылались на то, что было."""

    __tablename__ = "scenarios"
    __table_args__ = (
        UniqueConstraint("slug", "version", name="uq_scenarios_slug_version"),
        CheckConstraint(f"category IN {sql_in(CATEGORIES)}", name="category"),
        CheckConstraint("version >= 1", name="version_positive"),
        # Не больше одной активной версии на slug
        Index("uq_scenarios_active_slug", "slug", unique=True, postgresql_where=text("is_active")),
        Index("ix_scenarios_category_active", "category", "is_active"),
    )

    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    initial_message: Mapped[str | None] = mapped_column(Text)
    allowed_personas: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    requires_custom_situation: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("100"))
    # Скрытая часть: роль для промпта и критерии разбора — клиенту не отдаётся
    role_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evaluation_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
