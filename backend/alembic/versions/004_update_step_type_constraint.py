"""update agent_steps step_type check constraint for harness

Revision ID: 004
Revises: 2026_06_27_1449_6f56e7b3a5e7_add_chat_sessions_and_messages
Create Date: 2026-06-27 19:30:00.000000

The old constraint allowed:
  'reasoning', 'tool_call', 'observation', 'planning', 'decision', 'error'

The harness ReAct loop uses:
  'retrieve', 'reason', 'tool_call', 'synthesize', 'plan', 'reflect'
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "6f56e7b3a5e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_agent_steps_step_type_valid", "agent_steps", type_="check")
    op.create_check_constraint(
        "ck_agent_steps_step_type_valid",
        "agent_steps",
        "step_type IN ('retrieve', 'reason', 'tool_call', 'synthesize', 'plan', 'reflect')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_agent_steps_step_type_valid", "agent_steps", type_="check")
    op.create_check_constraint(
        "ck_agent_steps_step_type_valid",
        "agent_steps",
        "step_type IN ('reasoning', 'tool_call', 'observation', 'planning', 'decision', 'error')",
    )
