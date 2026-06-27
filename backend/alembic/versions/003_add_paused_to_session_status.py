"""Add 'paused' to agent_sessions status check constraint

Revision ID: 003
Revises: 002_update_users_role_constraint.py
Create Date: 2026-06-27 14:00:00.000000

"""

from typing import Sequence

from alembic import op

revision: str = "003"
down_revision: str | None = "002_update_users_role_constraint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL: alter check constraint (drop old, add new)
    op.execute(
        "ALTER TABLE agent_sessions DROP CONSTRAINT IF EXISTS ck_agent_sessions_status_valid"
    )
    op.execute(
        "ALTER TABLE agent_sessions ADD CONSTRAINT ck_agent_sessions_status_valid "
        "CHECK (status IN ('running', 'paused', 'completed', 'failed', 'cancelled', 'timeout'))"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE agent_sessions DROP CONSTRAINT IF EXISTS ck_agent_sessions_status_valid"
    )
    op.execute(
        "ALTER TABLE agent_sessions ADD CONSTRAINT ck_agent_sessions_status_valid "
        "CHECK (status IN ('running', 'completed', 'failed', 'cancelled', 'timeout'))"
    )
