"""add_ondelete_cascade_to_foreign_keys

Revision ID: 565106c3b23c
Revises: a3b4c5d6e7f8
Create Date: 2026-05-30 23:47:26.665280

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '565106c3b23c'
down_revision: Union[str, None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- activity_logs: SET NULL on agent/task/node deletion ---
    op.drop_constraint(op.f('activity_logs_agent_id_fkey'), 'activity_logs', type_='foreignkey')
    op.drop_constraint(op.f('activity_logs_node_id_fkey'), 'activity_logs', type_='foreignkey')
    op.drop_constraint(op.f('activity_logs_task_id_fkey'), 'activity_logs', type_='foreignkey')
    op.create_foreign_key('activity_logs_node_id_cascade_fkey', 'activity_logs', 'nodes', ['node_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('activity_logs_agent_id_cascade_fkey', 'activity_logs', 'agents', ['agent_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('activity_logs_task_id_cascade_fkey', 'activity_logs', 'tasks', ['task_id'], ['id'], ondelete='SET NULL')

    # --- agent_messages: CASCADE on agent deletion, SET NULL on task deletion ---
    op.drop_constraint(op.f('agent_messages_task_id_fkey'), 'agent_messages', type_='foreignkey')
    op.drop_constraint(op.f('agent_messages_from_agent_id_fkey'), 'agent_messages', type_='foreignkey')
    op.drop_constraint(op.f('agent_messages_to_agent_id_fkey'), 'agent_messages', type_='foreignkey')
    op.create_foreign_key('agent_messages_task_id_cascade_fkey', 'agent_messages', 'tasks', ['task_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('agent_messages_from_agent_id_cascade_fkey', 'agent_messages', 'agents', ['from_agent_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('agent_messages_to_agent_id_cascade_fkey', 'agent_messages', 'agents', ['to_agent_id'], ['id'], ondelete='CASCADE')

    # --- agents: SET NULL on supervisor agent deletion ---
    op.drop_constraint(op.f('agents_supervisor_agent_id_fkey'), 'agents', type_='foreignkey')
    op.create_foreign_key('agents_supervisor_agent_id_cascade_fkey', 'agents', 'agents', ['supervisor_agent_id'], ['id'], ondelete='SET NULL')

    # --- tasks: SET NULL on parent task / source agent deletion ---
    op.drop_constraint(op.f('tasks_parent_task_id_fkey'), 'tasks', type_='foreignkey')
    op.drop_constraint(op.f('tasks_source_agent_id_fkey'), 'tasks', type_='foreignkey')
    op.create_foreign_key('tasks_source_agent_id_cascade_fkey', 'tasks', 'agents', ['source_agent_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('tasks_parent_task_id_cascade_fkey', 'tasks', 'tasks', ['parent_task_id'], ['id'], ondelete='SET NULL')

    # --- terminal_sessions: CASCADE on agent deletion, SET NULL on node deletion ---
    op.drop_constraint(op.f('terminal_sessions_agent_id_fkey'), 'terminal_sessions', type_='foreignkey')
    op.drop_constraint(op.f('terminal_sessions_node_id_fkey'), 'terminal_sessions', type_='foreignkey')
    op.create_foreign_key('terminal_sessions_agent_id_cascade_fkey', 'terminal_sessions', 'agents', ['agent_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('terminal_sessions_node_id_cascade_fkey', 'terminal_sessions', 'nodes', ['node_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    # --- terminal_sessions: revert to RESTRICT (no ondelete) ---
    op.drop_constraint('terminal_sessions_node_id_cascade_fkey', 'terminal_sessions', type_='foreignkey')
    op.drop_constraint('terminal_sessions_agent_id_cascade_fkey', 'terminal_sessions', type_='foreignkey')
    op.create_foreign_key(op.f('terminal_sessions_node_id_fkey'), 'terminal_sessions', 'nodes', ['node_id'], ['id'])
    op.create_foreign_key(op.f('terminal_sessions_agent_id_fkey'), 'terminal_sessions', 'agents', ['agent_id'], ['id'])

    # --- tasks: revert ---
    op.drop_constraint('tasks_source_agent_id_cascade_fkey', 'tasks', type_='foreignkey')
    op.drop_constraint('tasks_parent_task_id_cascade_fkey', 'tasks', type_='foreignkey')
    op.create_foreign_key(op.f('tasks_source_agent_id_fkey'), 'tasks', 'agents', ['source_agent_id'], ['id'])
    op.create_foreign_key(op.f('tasks_parent_task_id_fkey'), 'tasks', 'tasks', ['parent_task_id'], ['id'])

    # --- agents: revert ---
    op.drop_constraint('agents_supervisor_agent_id_cascade_fkey', 'agents', type_='foreignkey')
    op.create_foreign_key(op.f('agents_supervisor_agent_id_fkey'), 'agents', 'agents', ['supervisor_agent_id'], ['id'])

    # --- agent_messages: revert ---
    op.drop_constraint('agent_messages_to_agent_id_cascade_fkey', 'agent_messages', type_='foreignkey')
    op.drop_constraint('agent_messages_from_agent_id_cascade_fkey', 'agent_messages', type_='foreignkey')
    op.drop_constraint('agent_messages_task_id_cascade_fkey', 'agent_messages', type_='foreignkey')
    op.create_foreign_key(op.f('agent_messages_to_agent_id_fkey'), 'agent_messages', 'agents', ['to_agent_id'], ['id'])
    op.create_foreign_key(op.f('agent_messages_from_agent_id_fkey'), 'agent_messages', 'agents', ['from_agent_id'], ['id'])
    op.create_foreign_key(op.f('agent_messages_task_id_fkey'), 'agent_messages', 'tasks', ['task_id'], ['id'])

    # --- activity_logs: revert ---
    op.drop_constraint('activity_logs_task_id_cascade_fkey', 'activity_logs', type_='foreignkey')
    op.drop_constraint('activity_logs_node_id_cascade_fkey', 'activity_logs', type_='foreignkey')
    op.drop_constraint('activity_logs_agent_id_cascade_fkey', 'activity_logs', type_='foreignkey')
    op.create_foreign_key(op.f('activity_logs_task_id_fkey'), 'activity_logs', 'tasks', ['task_id'], ['id'])
    op.create_foreign_key(op.f('activity_logs_node_id_fkey'), 'activity_logs', 'nodes', ['node_id'], ['id'])
    op.create_foreign_key(op.f('activity_logs_agent_id_fkey'), 'activity_logs', 'agents', ['agent_id'], ['id'])
