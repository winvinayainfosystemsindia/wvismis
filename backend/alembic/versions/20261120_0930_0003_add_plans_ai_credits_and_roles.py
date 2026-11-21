"""Add plans, AI credit wallets/transactions, and update organization columns

Revision ID: 0003_add_plans_ai_credits_and_roles
Revises: 0002_add_organization_hierarchy
Create Date: 2026-11-20 09:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0003_plans_ai_credits_roles"
down_revision: Union[str, None] = "0002_add_organization_hierarchy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Expand alembic_version version_num to accommodate future descriptive revisions
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128);")

    # 1. Update userrole enum with owner, member, viewer
    for role_val in ("owner", "member", "viewer"):
        op.execute(
            f"ALTER TYPE userrole ADD VALUE IF NOT EXISTS '{role_val}';"
        )

    # 2. Create plantier enum and plans table if not exists
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'plantier') THEN
                CREATE TYPE plantier AS ENUM ('free', 'basic', 'pro', 'enterprise');
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS plans (
            id SERIAL PRIMARY KEY,
            tier plantier NOT NULL UNIQUE,
            name VARCHAR(50) NOT NULL,
            enabled_modules JSONB NOT NULL DEFAULT '[]'::jsonb,
            ai_credits_monthly INTEGER NOT NULL DEFAULT 1000,
            user_limit INTEGER DEFAULT 100,
            price_per_user INTEGER NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            deleted_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
        );
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='plans' AND column_name='is_deleted') THEN
                ALTER TABLE plans ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='plans' AND column_name='deleted_at') THEN
                ALTER TABLE plans ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;
            END IF;
        END $$;
        """
    )

    # 3. Add organization columns
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='organizations' AND column_name='plan_id') THEN
                ALTER TABLE organizations ADD COLUMN plan_id INTEGER REFERENCES plans(id) ON DELETE SET NULL;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='organizations' AND column_name='subscription_status') THEN
                ALTER TABLE organizations ADD COLUMN subscription_status VARCHAR(50) DEFAULT 'active';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='organizations' AND column_name='trial_expires_at') THEN
                ALTER TABLE organizations ADD COLUMN trial_expires_at TIMESTAMP WITH TIME ZONE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='organizations' AND column_name='others') THEN
                ALTER TABLE organizations ADD COLUMN others JSONB DEFAULT '{}'::jsonb;
            END IF;
        END $$;
        """
    )

    # 4. Standardize max_users for default organization
    op.execute("UPDATE organizations SET max_users = 100 WHERE max_users = 100000;")
    op.execute("UPDATE plans SET user_limit = 100 WHERE tier = 'enterprise' AND (user_limit IS NULL OR user_limit > 100);")

    # 5. Create AI credit tables
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'aicredittransactionreason') THEN
                CREATE TYPE aicredittransactionreason AS ENUM ('monthly_grant', 'purchase', 'usage', 'admin_grant', 'adjustment', 'rollover', 'ai_call', 'admin_adjustment');
            END IF;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_credit_wallets (
            id SERIAL PRIMARY KEY,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            period_start TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            balance INTEGER NOT NULL DEFAULT 0,
            granted INTEGER NOT NULL DEFAULT 0,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            deleted_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            CONSTRAINT uq_ai_credit_wallet_org_user UNIQUE (organization_id, user_id)
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_credit_transactions (
            id SERIAL PRIMARY KEY,
            organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            wallet_id INTEGER NOT NULL REFERENCES ai_credit_wallets(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            amount INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            reason aicredittransactionreason NOT NULL,
            provider VARCHAR(50),
            model VARCHAR(100),
            action_type VARCHAR(50),
            tokens_used INTEGER,
            is_estimated BOOLEAN NOT NULL DEFAULT FALSE,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            deleted_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ai_credit_transactions CASCADE;")
    op.execute("DROP TABLE IF EXISTS ai_credit_wallets CASCADE;")
    op.execute("ALTER TABLE organizations DROP COLUMN IF EXISTS others;")
    op.execute("ALTER TABLE organizations DROP COLUMN IF EXISTS trial_expires_at;")
    op.execute("ALTER TABLE organizations DROP COLUMN IF EXISTS subscription_status;")
    op.execute("ALTER TABLE organizations DROP COLUMN IF EXISTS plan_id;")
    op.execute("DROP TABLE IF EXISTS plans CASCADE;")
