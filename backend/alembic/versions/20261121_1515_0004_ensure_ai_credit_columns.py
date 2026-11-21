"""Ensure ai_credit_wallets and transactions have all required columns

Revision ID: 0004_ensure_ai_credit_columns
Revises: 0003_plans_ai_credits_roles
Create Date: 2026-11-21 15:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0004_ensure_ai_credit_columns"
down_revision: Union[str, None] = "0003_plans_ai_credits_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Ensure columns on ai_credit_wallets
    op.execute(
        """
        DO $$
        BEGIN
            -- Ensure period_start column
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ai_credit_wallets' AND column_name='period_start') THEN
                ALTER TABLE ai_credit_wallets ADD COLUMN period_start TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;
            END IF;

            -- Ensure balance column
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ai_credit_wallets' AND column_name='balance') THEN
                ALTER TABLE ai_credit_wallets ADD COLUMN balance INTEGER NOT NULL DEFAULT 0;
            END IF;

            -- Ensure granted column
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ai_credit_wallets' AND column_name='granted') THEN
                ALTER TABLE ai_credit_wallets ADD COLUMN granted INTEGER NOT NULL DEFAULT 0;
            END IF;

            -- Ensure is_deleted column
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ai_credit_wallets' AND column_name='is_deleted') THEN
                ALTER TABLE ai_credit_wallets ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;

            -- Ensure deleted_at column
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ai_credit_wallets' AND column_name='deleted_at') THEN
                ALTER TABLE ai_credit_wallets ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;
            END IF;
        END $$;
        """
    )

    # 2. Ensure columns on ai_credit_transactions
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ai_credit_transactions' AND column_name='tokens_used') THEN
                ALTER TABLE ai_credit_transactions ADD COLUMN tokens_used INTEGER;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ai_credit_transactions' AND column_name='is_estimated') THEN
                ALTER TABLE ai_credit_transactions ADD COLUMN is_estimated BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ai_credit_transactions' AND column_name='is_deleted') THEN
                ALTER TABLE ai_credit_transactions ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='ai_credit_transactions' AND column_name='deleted_at') THEN
                ALTER TABLE ai_credit_transactions ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    pass
