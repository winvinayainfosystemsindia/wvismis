"""Initial WVISMIS schema: organizations, users, token_blacklist, activity_logs, system_settings, ai_chat_sessions, ai_task_logs, ai_chat_messages

Revision ID: 0001_initial_wvismis
Revises: 
Create Date: 2026-11-19 09:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_initial_wvismis"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=30), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column(
            "subscription_plan",
            sa.Enum("free", "starter", "professional", "enterprise", name="subscriptionplan"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("max_users", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_organizations_id"), "organizations", ["id"], unique=False)
    op.create_index(op.f("ix_organizations_public_id"), "organizations", ["public_id"], unique=True)
    op.create_index(op.f("ix_organizations_name"), "organizations", ["name"], unique=False)
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True)
    op.create_index(op.f("ix_organizations_domain"), "organizations", ["domain"], unique=True)
    op.create_index(op.f("ix_organizations_subscription_plan"), "organizations", ["subscription_plan"], unique=False)
    op.create_index(op.f("ix_organizations_is_active"), "organizations", ["is_active"], unique=False)
    op.create_index(op.f("ix_organizations_is_deleted"), "organizations", ["is_deleted"], unique=False)

    # 2. users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "role",
            sa.Enum(
                "super_admin",
                "org_admin",
                "admin",
                "manager",
                "sourcing",
                "trainer",
                "counselor",
                "placement",
                "project_coordinator",
                "developer",
                "user",
                name="userrole",
            ),
            nullable=False,
        ),
        sa.Column("mobile", sa.String(length=20), nullable=True),
        sa.Column("department", sa.String(length=100), nullable=True),
        sa.Column("designation", sa.String(length=100), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_public_id"), "users", ["public_id"], unique=True)
    op.create_index(op.f("ix_users_organization_id"), "users", ["organization_id"], unique=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)
    op.create_index(op.f("ix_users_mobile"), "users", ["mobile"], unique=False)
    op.create_index(op.f("ix_users_department"), "users", ["department"], unique=False)
    op.create_index(op.f("ix_users_is_deleted"), "users", ["is_deleted"], unique=False)

    # 3. token_blacklist table
    op.create_table(
        "token_blacklist",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("jti", sa.String(length=100), nullable=False),
        sa.Column("token_type", sa.String(length=20), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_token_blacklist_id"), "token_blacklist", ["id"], unique=False)
    op.create_index(op.f("ix_token_blacklist_jti"), "token_blacklist", ["jti"], unique=True)
    op.create_index(op.f("ix_token_blacklist_user_id"), "token_blacklist", ["user_id"], unique=False)
    op.create_index(op.f("ix_token_blacklist_expires_at"), "token_blacklist", ["expires_at"], unique=False)
    op.create_index(op.f("ix_token_blacklist_is_deleted"), "token_blacklist", ["is_deleted"], unique=False)

    # 4. activity_logs table
    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column(
            "action_type",
            sa.Enum("create", "read", "update", "delete", "login", "logout", name="actiontype"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("changes", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_activity_logs_id"), "activity_logs", ["id"], unique=False)
    op.create_index(op.f("ix_activity_logs_organization_id"), "activity_logs", ["organization_id"], unique=False)
    op.create_index(op.f("ix_activity_logs_user_id"), "activity_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_activity_logs_action_type"), "activity_logs", ["action_type"], unique=False)
    op.create_index(op.f("ix_activity_logs_resource_type"), "activity_logs", ["resource_type"], unique=False)
    op.create_index(op.f("ix_activity_logs_is_deleted"), "activity_logs", ["is_deleted"], unique=False)

    # 5. system_settings table
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_system_settings_id"), "system_settings", ["id"], unique=False)
    op.create_index(op.f("ix_system_settings_organization_id"), "system_settings", ["organization_id"], unique=False)
    op.create_index(op.f("ix_system_settings_key"), "system_settings", ["key"], unique=False)
    op.create_index(op.f("ix_system_settings_is_deleted"), "system_settings", ["is_deleted"], unique=False)

    # 6. ai_chat_sessions table
    op.create_table(
        "ai_chat_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_chat_sessions_id"), "ai_chat_sessions", ["id"], unique=False)
    op.create_index(op.f("ix_ai_chat_sessions_public_id"), "ai_chat_sessions", ["public_id"], unique=True)
    op.create_index(op.f("ix_ai_chat_sessions_organization_id"), "ai_chat_sessions", ["organization_id"], unique=False)
    op.create_index(op.f("ix_ai_chat_sessions_user_id"), "ai_chat_sessions", ["user_id"], unique=False)
    op.create_index(op.f("ix_ai_chat_sessions_is_deleted"), "ai_chat_sessions", ["is_deleted"], unique=False)

    # 7. ai_task_logs table
    op.create_table(
        "ai_task_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("task_name", sa.String(length=255), nullable=False),
        sa.Column(
            "trigger",
            sa.Enum("manual", "webhook", "schedule", "api", "websocket", "system", name="aitasktrigger"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "planning",
                "running",
                "awaiting_approval",
                "completed",
                "partially_completed",
                "failed",
                "cancelled",
                name="aitaskstatus",
            ),
            nullable=False,
        ),
        sa.Column("triggered_by_user_id", sa.Integer(), nullable=True),
        sa.Column("chat_session_id", sa.Integer(), nullable=True),
        sa.Column("ai_provider", sa.String(length=50), nullable=True),
        sa.Column("ai_model", sa.String(length=100), nullable=True),
        sa.Column("raw_input", sa.JSON(), nullable=True),
        sa.Column("context_snapshot", sa.JSON(), nullable=True),
        sa.Column("plan", sa.JSON(), nullable=True),
        sa.Column("plan_reasoning", sa.Text(), nullable=True),
        sa.Column("steps", sa.JSON(), nullable=True),
        sa.Column("tools_called", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tools_succeeded", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tools_failed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("records_affected", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("llm_tokens_used", sa.Integer(), nullable=True),
        sa.Column("llm_cost_usd", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["chat_session_id"], ["ai_chat_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["triggered_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_task_logs_id"), "ai_task_logs", ["id"], unique=False)
    op.create_index(op.f("ix_ai_task_logs_public_id"), "ai_task_logs", ["public_id"], unique=True)
    op.create_index(op.f("ix_ai_task_logs_organization_id"), "ai_task_logs", ["organization_id"], unique=False)
    op.create_index(op.f("ix_ai_task_logs_task_name"), "ai_task_logs", ["task_name"], unique=False)
    op.create_index(op.f("ix_ai_task_logs_trigger"), "ai_task_logs", ["trigger"], unique=False)
    op.create_index(op.f("ix_ai_task_logs_status"), "ai_task_logs", ["status"], unique=False)
    op.create_index(op.f("ix_ai_task_logs_triggered_by_user_id"), "ai_task_logs", ["triggered_by_user_id"], unique=False)
    op.create_index(op.f("ix_ai_task_logs_chat_session_id"), "ai_task_logs", ["chat_session_id"], unique=False)
    op.create_index(op.f("ix_ai_task_logs_is_deleted"), "ai_task_logs", ["is_deleted"], unique=False)

    # 8. ai_chat_messages table
    op.create_table(
        "ai_chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=True),
        sa.Column("task_log_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["ai_chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_log_id"], ["ai_task_logs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_chat_messages_id"), "ai_chat_messages", ["id"], unique=False)
    op.create_index(op.f("ix_ai_chat_messages_session_id"), "ai_chat_messages", ["session_id"], unique=False)
    op.create_index(op.f("ix_ai_chat_messages_task_log_id"), "ai_chat_messages", ["task_log_id"], unique=False)
    op.create_index(op.f("ix_ai_chat_messages_is_deleted"), "ai_chat_messages", ["is_deleted"], unique=False)


def downgrade() -> None:
    op.drop_table("ai_chat_messages")
    op.drop_table("ai_task_logs")
    op.drop_table("ai_chat_sessions")
    op.drop_table("system_settings")
    op.drop_table("activity_logs")
    op.drop_table("token_blacklist")
    op.drop_table("users")
    op.drop_table("organizations")
