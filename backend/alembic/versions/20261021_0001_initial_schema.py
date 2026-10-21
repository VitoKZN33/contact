"""initial schema: users, sessions, scenarios, trainings, messages, results, ai usage

Revision ID: 0001
Revises:
Create Date: 2026-10-21

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()
TS = sa.DateTime(timezone=True)


def _now() -> sa.TextClause:
    return sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID, nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("display_name", sa.String(128), nullable=True),
        sa.Column("locale", sa.String(16), nullable=True),
        sa.Column("plan", sa.String(16), server_default=sa.text("'free'"), nullable=False),
        sa.Column("notifications_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("status", sa.String(16), server_default=sa.text("'active'"), nullable=False),
        sa.Column("last_active_at", TS, server_default=_now(), nullable=False),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
        sa.Column("updated_at", TS, server_default=_now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'blocked')", name=op.f("ck_users_status")),
        sa.CheckConstraint("plan IN ('free')", name=op.f("ck_users_plan")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("telegram_user_id", name=op.f("uq_users_telegram_user_id")),
    )

    op.create_table(
        "scenarios",
        sa.Column("id", UUID, nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("initial_message", sa.Text(), nullable=True),
        sa.Column("allowed_personas", JSONB, nullable=False),
        sa.Column("requires_custom_situation", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("100"), nullable=False),
        sa.Column("role_config", JSONB, nullable=False),
        sa.Column("evaluation_config", JSONB, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
        sa.Column("updated_at", TS, server_default=_now(), nullable=False),
        sa.CheckConstraint(
            "category IN ('acquaintance', 'small_talk', 'events', 'first_date', 'messaging', 'opinion', "
            "'saying_no', 'boundaries', 'criticism', 'conflict', 'favor', 'custom')",
            name=op.f("ck_scenarios_category"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_scenarios_version_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenarios")),
        sa.UniqueConstraint("slug", "version", name="uq_scenarios_slug_version"),
    )
    op.create_index(
        "uq_scenarios_active_slug", "scenarios", ["slug"], unique=True, postgresql_where=sa.text("is_active")
    )
    op.create_index("ix_scenarios_category_active", "scenarios", ["category", "is_active"])

    op.create_table(
        "auth_sessions",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("revoked_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_auth_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_auth_sessions_token_hash")),
    )
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"])

    op.create_table(
        "training_sessions",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("scenario_id", UUID, nullable=False),
        sa.Column("custom_situation", sa.Text(), nullable=True),
        sa.Column("persona_type", sa.String(32), nullable=False),
        sa.Column("persona_gender", sa.String(16), nullable=False),
        sa.Column("persona_name", sa.String(64), nullable=False),
        sa.Column("difficulty", sa.String(16), nullable=False),
        sa.Column("interaction_mode", sa.String(16), server_default=sa.text("'text'"), nullable=False),
        sa.Column("status", sa.String(16), server_default=sa.text("'active'"), nullable=False),
        sa.Column("analysis_status", sa.String(16), server_default=sa.text("'none'"), nullable=False),
        sa.Column("context_summary", sa.Text(), nullable=True),
        sa.Column("message_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column("started_at", TS, server_default=_now(), nullable=False),
        sa.Column("last_message_at", TS, server_default=_now(), nullable=False),
        sa.Column("completed_at", TS, nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'completed', 'abandoned', 'expired')", name=op.f("ck_training_sessions_status")
        ),
        sa.CheckConstraint(
            "analysis_status IN ('none', 'pending', 'done', 'failed')",
            name=op.f("ck_training_sessions_analysis_status"),
        ),
        sa.CheckConstraint(
            "persona_type IN ('friendly', 'neutral', 'reserved', 'shy', 'sociable', 'skeptical', "
            "'demanding', 'unpredictable')",
            name=op.f("ck_training_sessions_persona_type"),
        ),
        sa.CheckConstraint("persona_gender IN ('male', 'female')", name=op.f("ck_training_sessions_persona_gender")),
        sa.CheckConstraint("difficulty IN ('easy', 'medium', 'hard')", name=op.f("ck_training_sessions_difficulty")),
        sa.CheckConstraint("interaction_mode IN ('text')", name=op.f("ck_training_sessions_interaction_mode")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_training_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios.id"],
            name=op.f("fk_training_sessions_scenario_id_scenarios"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_sessions")),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_training_sessions_user_idempotency"),
    )
    op.create_index(op.f("ix_training_sessions_scenario_id"), "training_sessions", ["scenario_id"])
    op.create_index(
        "uq_training_sessions_active_user",
        "training_sessions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index("ix_training_sessions_user_completed", "training_sessions", ["user_id", "completed_at"])

    op.create_table(
        "messages",
        sa.Column("id", UUID, nullable=False),
        sa.Column("session_id", UUID, nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("input_mode", sa.String(16), server_default=sa.text("'text'"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("client_message_id", sa.String(64), nullable=True),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'persona')", name=op.f("ck_messages_role")),
        sa.CheckConstraint("status IN ('accepted', 'completed', 'failed')", name=op.f("ck_messages_status")),
        sa.CheckConstraint("input_mode IN ('text')", name=op.f("ck_messages_input_mode")),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["training_sessions.id"],
            name=op.f("fk_messages_session_id_training_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
        sa.UniqueConstraint("session_id", "sequence_number", name="uq_messages_session_sequence"),
        sa.UniqueConstraint("session_id", "client_message_id", name="uq_messages_session_client_id"),
    )

    op.create_table(
        "training_results",
        sa.Column("id", UUID, nullable=False),
        sa.Column("session_id", UUID, nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("strengths", JSONB, nullable=False),
        sa.Column("improvement_points", JSONB, nullable=False),
        sa.Column("alternative_replies", JSONB, nullable=False),
        sa.Column("scores", JSONB, nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["training_sessions.id"],
            name=op.f("fk_training_results_session_id_training_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_results")),
        sa.UniqueConstraint("session_id", name=op.f("uq_training_results_session_id")),
    )

    op.create_table(
        "ai_usage",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=True),
        sa.Column("session_id", UUID, nullable=True),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_cached", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
        sa.CheckConstraint(
            "operation IN ('reply', 'summary', 'analysis')", name=op.f("ck_ai_usage_operation")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_ai_usage_user_id_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["training_sessions.id"],
            name=op.f("fk_ai_usage_session_id_training_sessions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_usage")),
    )
    op.create_index(op.f("ix_ai_usage_user_id"), "ai_usage", ["user_id"])
    op.create_index(op.f("ix_ai_usage_session_id"), "ai_usage", ["session_id"])
    op.create_index(op.f("ix_ai_usage_created_at"), "ai_usage", ["created_at"])


def downgrade() -> None:
    op.drop_table("ai_usage")
    op.drop_table("training_results")
    op.drop_table("messages")
    op.drop_table("training_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("scenarios")
    op.drop_table("users")
