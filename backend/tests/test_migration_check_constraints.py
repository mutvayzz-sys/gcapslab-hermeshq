"""Tests for Alembic migration b1c2d3e4f5a6: add check constraints for status columns."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MIG_PATH = (
    "hermeshq.alembic.versions."
    "b1c2d3e4f5a6_add_check_constraints_for_status_columns"
)


def _import_migration():
    """Import the migration module fresh."""
    import importlib
    import hermeshq.alembic.versions.b1c2d3e4f5a6_add_check_constraints_for_status_columns as mod
    importlib.reload(mod)
    return mod


# ---------------------------------------------------------------------------
# _constraint_exists
# ---------------------------------------------------------------------------

class TestConstraintExists:
    def test_returns_true_when_found(self):
        mod = _import_migration()
        mock_op = MagicMock()
        mock_bind = MagicMock()
        mock_op.get_bind.return_value = mock_bind

        mock_inspect = MagicMock()
        mock_inspect_instance = MagicMock()
        mock_inspect_instance.get_check_constraints.return_value = [
            {"name": "ck_agents_status"},
            {"name": "other_constraint"},
        ]
        mock_inspect.return_value = mock_inspect_instance

        with patch(f"{MIG_PATH}.op", mock_op), \
             patch(f"{MIG_PATH}.inspect", mock_inspect):
            result = mod._constraint_exists("agents", "ck_agents_status")

        assert result is True

    def test_returns_false_when_not_found(self):
        mod = _import_migration()
        mock_op = MagicMock()
        mock_bind = MagicMock()
        mock_op.get_bind.return_value = mock_bind

        mock_inspect = MagicMock()
        mock_inspect_instance = MagicMock()
        mock_inspect_instance.get_check_constraints.return_value = [
            {"name": "other_constraint"},
        ]
        mock_inspect.return_value = mock_inspect_instance

        with patch(f"{MIG_PATH}.op", mock_op), \
             patch(f"{MIG_PATH}.inspect", mock_inspect):
            result = mod._constraint_exists("agents", "ck_agents_status")

        assert result is False

    def test_returns_false_when_empty(self):
        mod = _import_migration()
        mock_op = MagicMock()
        mock_bind = MagicMock()
        mock_op.get_bind.return_value = mock_bind

        mock_inspect = MagicMock()
        mock_inspect_instance = MagicMock()
        mock_inspect_instance.get_check_constraints.return_value = []
        mock_inspect.return_value = mock_inspect_instance

        with patch(f"{MIG_PATH}.op", mock_op), \
             patch(f"{MIG_PATH}.inspect", mock_inspect):
            result = mod._constraint_exists("agents", "ck_agents_status")

        assert result is False

    def test_inspects_correct_table(self):
        mod = _import_migration()
        mock_op = MagicMock()
        mock_op.get_bind.return_value = MagicMock()

        mock_inspect = MagicMock()
        mock_inspect_instance = MagicMock()
        mock_inspect_instance.get_check_constraints.return_value = []
        mock_inspect.return_value = mock_inspect_instance

        with patch(f"{MIG_PATH}.op", mock_op), \
             patch(f"{MIG_PATH}.inspect", mock_inspect):
            mod._constraint_exists("tasks", "ck_tasks_status")

        mock_inspect_instance.get_check_constraints.assert_called_once_with("tasks")


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------

class TestUpgrade:
    def test_creates_both_constraints_when_missing(self):
        mod = _import_migration()
        mock_op = MagicMock()

        with patch(f"{MIG_PATH}.op", mock_op), \
             patch.object(mod, "_constraint_exists", return_value=False):
            mod.upgrade()

        assert mock_op.create_check_constraint.call_count == 2

        names = [c[0][0] for c in mock_op.create_check_constraint.call_args_list]
        assert "ck_agents_status" in names
        assert "ck_tasks_status" in names

    def test_skips_agents_constraint_when_exists(self):
        mod = _import_migration()
        mock_op = MagicMock()

        def side_effect(table, name):
            return name == "ck_agents_status"

        with patch(f"{MIG_PATH}.op", mock_op), \
             patch.object(mod, "_constraint_exists", side_effect=side_effect):
            mod.upgrade()

        assert mock_op.create_check_constraint.call_count == 1
        assert mock_op.create_check_constraint.call_args[0][0] == "ck_tasks_status"

    def test_skips_tasks_constraint_when_exists(self):
        mod = _import_migration()
        mock_op = MagicMock()

        def side_effect(table, name):
            return name == "ck_tasks_status"

        with patch(f"{MIG_PATH}.op", mock_op), \
             patch.object(mod, "_constraint_exists", side_effect=side_effect):
            mod.upgrade()

        assert mock_op.create_check_constraint.call_count == 1
        assert mock_op.create_check_constraint.call_args[0][0] == "ck_agents_status"

    def test_skips_all_when_both_exist(self):
        mod = _import_migration()
        mock_op = MagicMock()

        with patch(f"{MIG_PATH}.op", mock_op), \
             patch.object(mod, "_constraint_exists", return_value=True):
            mod.upgrade()

        mock_op.create_check_constraint.assert_not_called()

    def test_agents_constraint_values(self):
        mod = _import_migration()
        mock_op = MagicMock()

        with patch(f"{MIG_PATH}.op", mock_op), \
             patch.object(mod, "_constraint_exists", return_value=False):
            mod.upgrade()

        agents_calls = [
            c for c in mock_op.create_check_constraint.call_args_list
            if c[0][0] == "ck_agents_status"
        ]
        assert len(agents_calls) == 1
        ac = agents_calls[0]
        assert ac[0][1] == "agents"
        assert "stopped" in ac[0][2]
        assert "running" in ac[0][2]
        assert "error" in ac[0][2]
        assert "starting" in ac[0][2]

    def test_tasks_constraint_values(self):
        mod = _import_migration()
        mock_op = MagicMock()

        with patch(f"{MIG_PATH}.op", mock_op), \
             patch.object(mod, "_constraint_exists", return_value=False):
            mod.upgrade()

        tasks_calls = [
            c for c in mock_op.create_check_constraint.call_args_list
            if c[0][0] == "ck_tasks_status"
        ]
        assert len(tasks_calls) == 1
        tc = tasks_calls[0]
        assert tc[0][1] == "tasks"
        for status in ("pending", "queued", "running", "completed", "failed", "cancelled"):
            assert status in tc[0][2]


# ---------------------------------------------------------------------------
# downgrade
# ---------------------------------------------------------------------------

class TestDowngrade:
    def test_drops_both_constraints_when_exist(self):
        mod = _import_migration()
        mock_op = MagicMock()

        with patch(f"{MIG_PATH}.op", mock_op), \
             patch.object(mod, "_constraint_exists", return_value=True):
            mod.downgrade()

        assert mock_op.drop_constraint.call_count == 2
        names = [c[0][0] for c in mock_op.drop_constraint.call_args_list]
        assert "ck_agents_status" in names
        assert "ck_tasks_status" in names

    def test_skips_agents_drop_when_missing(self):
        mod = _import_migration()
        mock_op = MagicMock()

        def side_effect(table, name):
            return name == "ck_tasks_status"

        with patch(f"{MIG_PATH}.op", mock_op), \
             patch.object(mod, "_constraint_exists", side_effect=side_effect):
            mod.downgrade()

        assert mock_op.drop_constraint.call_count == 1
        assert mock_op.drop_constraint.call_args[0][0] == "ck_tasks_status"

    def test_skips_all_when_none_exist(self):
        mod = _import_migration()
        mock_op = MagicMock()

        with patch(f"{MIG_PATH}.op", mock_op), \
             patch.object(mod, "_constraint_exists", return_value=False):
            mod.downgrade()

        mock_op.drop_constraint.assert_not_called()

    def test_drop_uses_check_type(self):
        mod = _import_migration()
        mock_op = MagicMock()

        with patch(f"{MIG_PATH}.op", mock_op), \
             patch.object(mod, "_constraint_exists", return_value=True):
            mod.downgrade()

        for c in mock_op.drop_constraint.call_args_list:
            assert c[1].get("type_") == "check"


# ---------------------------------------------------------------------------
# Revision metadata
# ---------------------------------------------------------------------------

class TestRevisionMetadata:
    def test_revision_id(self):
        mod = _import_migration()
        assert mod.revision == "b1c2d3e4f5a6"

    def test_down_revision(self):
        mod = _import_migration()
        assert mod.down_revision == "a3b4c5d6e7f8"

    def test_no_branch_labels(self):
        mod = _import_migration()
        assert mod.branch_labels is None

    def test_no_depends_on(self):
        mod = _import_migration()
        assert mod.depends_on is None
