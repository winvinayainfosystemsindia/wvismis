"""Add organization hierarchy (parent_id, is_parent) and enforce organization_id on users

Revision ID: 0002_add_organization_hierarchy
Revises: 0001_initial_wvismis
Create Date: 2026-11-19 10:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002_add_organization_hierarchy"
down_revision: Union[str, None] = "0001_initial_wvismis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add hierarchical parent_id and is_parent flag to organizations
    op.add_column(
        "organizations",
        sa.Column("parent_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("is_parent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_foreign_key(
        "fk_organizations_parent_id",
        "organizations",
        "organizations",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_organizations_parent_id"),
        "organizations",
        ["parent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_organizations_is_parent"),
        "organizations",
        ["is_parent"],
        unique=False,
    )

    # 2. Backfill any existing users without an organization before making it non-nullable
    # Uses raw SQL with PostgreSQL DO block for safe fallback
    op.execute(
        """
        DO $$
        DECLARE
            default_org_id INTEGER;
        BEGIN
            -- Try to find WinVinaya parent org
            SELECT id INTO default_org_id FROM organizations WHERE slug = 'winvinaya' LIMIT 1;
            
            -- If not found, use earliest created organization
            IF default_org_id IS NULL THEN
                SELECT id INTO default_org_id FROM organizations ORDER BY id ASC LIMIT 1;
            END IF;

            -- Assign to any unassociated users
            IF default_org_id IS NOT NULL THEN
                UPDATE users SET organization_id = default_org_id WHERE organization_id IS NULL;
            END IF;
        END $$;
        """
    )

    # 3. Alter users.organization_id to NOT NULL
    op.alter_column(
        "users",
        "organization_id",
        existing_type=sa.Integer(),
        nullable=False,
    )


def downgrade() -> None:
    # 1. Allow nullable organization_id on users
    op.alter_column(
        "users",
        "organization_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    # 2. Drop indices from organizations
    op.drop_index(op.f("ix_organizations_is_parent"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_parent_id"), table_name="organizations")

    # 3. Drop foreign key and columns from organizations
    op.drop_constraint("fk_organizations_parent_id", "organizations", type_="foreignkey")
    op.drop_column("organizations", "is_parent")
    op.drop_column("organizations", "parent_id")
