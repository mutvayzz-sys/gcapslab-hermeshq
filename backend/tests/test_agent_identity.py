"""Unit tests for hermeshq.services.agent_identity.

The source module uses ``str | None`` annotations (Python 3.10+) so we load it
dynamically with ``from __future__ import annotations`` prepended to ensure
compatibility with older Python runtimes.
"""

import os
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Bootstrap: load the module under test in a way that works on Python 3.9+
# ---------------------------------------------------------------------------

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_PATH = os.path.join(_BACKEND_DIR, "hermeshq", "services", "agent_identity.py")


def _load_module():
    """Load agent_identity.py with future annotations enabled."""
    # Stub out the heavy model dependency so we don't need SQLAlchemy models.
    _stub_agent = type("Agent", (), {
        "id": property(lambda self: None),
        "slug": property(lambda self: None),
    })
    _mock_agent_mod = types.ModuleType("hermeshq.models.agent")
    _mock_agent_mod.Agent = _stub_agent

    # Temporarily replace the module so agent_identity.py compiles against the
    # stub. We restore the original afterwards to avoid polluting sys.modules
    # and breaking other test files that import the real SQLAlchemy Agent model.
    _original_agent_mod = sys.modules.get("hermeshq.models.agent")
    sys.modules["hermeshq.models.agent"] = _mock_agent_mod
    try:
        with open(_SRC_PATH, "r") as f:
            source = f.read()

        # Inject future annotations so ``str | None`` works on Python 3.9.
        source = "from __future__ import annotations\n" + source

        mod = types.ModuleType("hermeshq.services.agent_identity")
        mod.__file__ = _SRC_PATH
        exec(compile(source, _SRC_PATH, "exec"), mod.__dict__)
        sys.modules["hermeshq.services.agent_identity"] = mod
    finally:
        if _original_agent_mod is not None:
            sys.modules["hermeshq.models.agent"] = _original_agent_mod
        else:
            sys.modules.pop("hermeshq.models.agent", None)
    return mod


_mod = _load_module()

slugify_agent_value = _mod.slugify_agent_value
derive_agent_identity = _mod.derive_agent_identity
ensure_unique_agent_slug = _mod.ensure_unique_agent_slug


# ---------------------------------------------------------------------------
# slugify_agent_value
# ---------------------------------------------------------------------------


class TestSlugifyAgentValue(unittest.TestCase):
    """Tests for the slugify_agent_value helper."""

    def test_normal_string(self):
        self.assertEqual(slugify_agent_value("My Agent"), "my-agent")

    def test_accented_characters(self):
        self.assertEqual(slugify_agent_value("Asistente Táctico"), "asistente-tactico")

    def test_special_chars_stripped(self):
        self.assertEqual(slugify_agent_value("Agent #1!"), "agent-1")

    def test_none_returns_default(self):
        self.assertEqual(slugify_agent_value(None), "agent")

    def test_empty_string_returns_default(self):
        self.assertEqual(slugify_agent_value(""), "agent")

    def test_whitespace_only_returns_default(self):
        self.assertEqual(slugify_agent_value("   "), "agent")

    def test_unicode_emojis_removed(self):
        self.assertEqual(slugify_agent_value("🤖 Robot"), "robot")

    def test_long_string_truncated_to_96(self):
        long_val = "a" * 200
        result = slugify_agent_value(long_val)
        self.assertEqual(len(result), 96)
        self.assertEqual(result, "a" * 96)

    def test_multiple_spaces_and_dashes_collapsed(self):
        self.assertEqual(slugify_agent_value("  my   agent  "), "my-agent")

    def test_consecutive_special_chars_collapsed(self):
        self.assertEqual(slugify_agent_value("hello!!!world"), "hello-world")

    def test_numbers_preserved(self):
        self.assertEqual(slugify_agent_value("Agent 42"), "agent-42")

    def test_leading_trailing_dashes_stripped(self):
        self.assertEqual(slugify_agent_value("---hello---"), "hello")

    def test_mixed_case_lowered(self):
        self.assertEqual(slugify_agent_value("ShOuTcAsE"), "shoutcase")

    def test_tab_and_newline_treated_as_separators(self):
        self.assertEqual(slugify_agent_value("hello\tworld\nfoo"), "hello-world-foo")

    def test_german_umlauts_transliterated(self):
        # ü → u after NFKD + ASCII filter; ß is stripped (non-ASCII)
        self.assertEqual(slugify_agent_value("Über Größe"), "uber-groe")


# ---------------------------------------------------------------------------
# derive_agent_identity
# ---------------------------------------------------------------------------


class TestDeriveAgentIdentity(unittest.TestCase):
    """Tests for the derive_agent_identity function."""

    def test_all_provided(self):
        friendly, name, slug = derive_agent_identity(
            friendly_name="Friendly",
            name="Name",
            slug="my-slug",
        )
        self.assertEqual(friendly, "Friendly")
        self.assertEqual(name, "Name")
        self.assertEqual(slug, "my-slug")

    def test_only_friendly_name(self):
        friendly, name, slug = derive_agent_identity(
            friendly_name="My Agent",
            name=None,
            slug=None,
        )
        self.assertEqual(friendly, "My Agent")
        self.assertEqual(name, "My Agent")
        self.assertEqual(slug, "my-agent")

    def test_only_name(self):
        friendly, name, slug = derive_agent_identity(
            friendly_name=None,
            name="Internal Name",
            slug=None,
        )
        self.assertEqual(friendly, "Internal Name")
        self.assertEqual(name, "Internal Name")
        self.assertEqual(slug, "internal-name")

    def test_all_none_returns_defaults(self):
        friendly, name, slug = derive_agent_identity(
            friendly_name=None,
            name=None,
            slug=None,
        )
        self.assertEqual(friendly, "Agent")
        self.assertEqual(name, "Agent")
        self.assertEqual(slug, "agent")

    def test_slug_explicitly_provided_not_derived(self):
        friendly, name, slug = derive_agent_identity(
            friendly_name="Friendly",
            name="Name",
            slug="custom-slug",
        )
        self.assertEqual(slug, "custom-slug")

    def test_empty_strings_treated_as_none(self):
        friendly, name, slug = derive_agent_identity(
            friendly_name="",
            name="",
            slug="",
        )
        # All empty → falls through to defaults
        self.assertEqual(friendly, "Agent")
        self.assertEqual(name, "Agent")
        self.assertEqual(slug, "agent")

    def test_friendly_name_whitespace_only(self):
        friendly, name, slug = derive_agent_identity(
            friendly_name="   ",
            name="Bot",
            slug=None,
        )
        self.assertEqual(friendly, "Bot")
        self.assertEqual(name, "Bot")
        self.assertEqual(slug, "bot")

    def test_name_empty_falls_back_to_friendly(self):
        friendly, name, slug = derive_agent_identity(
            friendly_name="Friendly",
            name="",
            slug=None,
        )
        self.assertEqual(name, "Friendly")
        self.assertEqual(slug, "friendly")

    def test_slug_empty_uses_friendly(self):
        friendly, name, slug = derive_agent_identity(
            friendly_name="Friendly",
            name="Name",
            slug="",
        )
        self.assertEqual(slug, "friendly")

    def test_slug_whitespace_uses_friendly(self):
        friendly, name, slug = derive_agent_identity(
            friendly_name="Friendly",
            name="Name",
            slug="   ",
        )
        self.assertEqual(slug, "friendly")

    def test_preserves_friendly_name_with_accents(self):
        friendly, name, slug = derive_agent_identity(
            friendly_name="Asistente Táctico",
            name=None,
            slug=None,
        )
        self.assertEqual(friendly, "Asistente Táctico")
        self.assertEqual(name, "Asistente Táctico")
        self.assertEqual(slug, "asistente-tactico")


# ---------------------------------------------------------------------------
# ensure_unique_agent_slug
#
# We patch ``select`` to avoid needing real SQLAlchemy column descriptors.
# The real function builds ``select(Agent.id).where(Agent.slug == candidate)``
# so we mock the chained query builder.
# ---------------------------------------------------------------------------


def _build_select_mock():
    """Return a mock ``select`` callable that mimics the SQLAlchemy chain.

    Usage inside the source:
        query = select(Agent.id).where(Agent.slug == candidate)
        if exclude_agent_id:
            query = query.where(Agent.id != exclude_agent_id)
    """
    query_mock = MagicMock()
    query_mock.where.return_value = query_mock  # .where() is chainable
    select_fn = MagicMock(return_value=query_mock)
    return select_fn


class TestEnsureUniqueAgentSlug(unittest.IsolatedAsyncioTestCase):
    """Tests for the async ensure_unique_agent_slug function."""

    @staticmethod
    def _make_db_result(scalar_value):
        """Helper to build a mock db.execute return value."""
        result = MagicMock()
        result.scalar_one_or_none.return_value = scalar_value
        return result

    async def test_no_collision_returns_original(self):
        """When no agent with the slug exists, return the slug as-is."""
        db = AsyncMock()
        db.execute.return_value = self._make_db_result(None)

        with patch.object(_mod, "select", _build_select_mock()):
            result = await ensure_unique_agent_slug(db, "my-agent")

        self.assertEqual(result, "my-agent")
        db.execute.assert_awaited_once()

    async def test_single_collision_appends_suffix_2(self):
        """When the slug is taken, return slug-2."""
        db = AsyncMock()
        db.execute.side_effect = [
            self._make_db_result("some-agent-id"),  # collision
            self._make_db_result(None),              # free
        ]

        with patch.object(_mod, "select", _build_select_mock()):
            result = await ensure_unique_agent_slug(db, "my-agent")

        self.assertEqual(result, "my-agent-2")
        self.assertEqual(db.execute.await_count, 2)

    async def test_multiple_collisions(self):
        """When slug, slug-2, slug-3 are all taken, return slug-4."""
        db = AsyncMock()
        db.execute.side_effect = [
            self._make_db_result("id1"),  # my-agent taken
            self._make_db_result("id2"),  # my-agent-2 taken
            self._make_db_result("id3"),  # my-agent-3 taken
            self._make_db_result(None),   # my-agent-4 free
        ]

        with patch.object(_mod, "select", _build_select_mock()):
            result = await ensure_unique_agent_slug(db, "my-agent")

        self.assertEqual(result, "my-agent-4")
        self.assertEqual(db.execute.await_count, 4)

    async def test_exclude_agent_id_parameter(self):
        """exclude_agent_id is passed through to the query builder."""
        db = AsyncMock()
        db.execute.return_value = self._make_db_result(None)

        select_mock = _build_select_mock()
        with patch.object(_mod, "select", select_mock):
            result = await ensure_unique_agent_slug(
                db, "my-agent", exclude_agent_id="exclude-me"
            )

        self.assertEqual(result, "my-agent")
        # .where() should have been called twice: once for slug, once for exclude
        query_obj = select_mock.return_value
        self.assertEqual(query_obj.where.call_count, 2)

    async def test_exclude_agent_id_allows_reuse(self):
        """When exclude_agent_id excludes the only match, slug is returned."""
        db = AsyncMock()
        db.execute.return_value = self._make_db_result(None)

        with patch.object(_mod, "select", _build_select_mock()):
            result = await ensure_unique_agent_slug(
                db, "taken-slug", exclude_agent_id="the-excluded-id"
            )

        self.assertEqual(result, "taken-slug")

    async def test_slug_is_re_slugified(self):
        """The input slug is passed through slugify_agent_value."""
        db = AsyncMock()
        db.execute.return_value = self._make_db_result(None)

        with patch.object(_mod, "select", _build_select_mock()):
            result = await ensure_unique_agent_slug(db, "My Custom Slug!")

        self.assertEqual(result, "my-custom-slug")

    async def test_collision_with_re_slugified_base(self):
        """Collision detection uses the slugified base, not the raw input."""
        db = AsyncMock()
        db.execute.side_effect = [
            self._make_db_result("id"),  # collision on slugified base
            self._make_db_result(None),  # free
        ]

        with patch.object(_mod, "select", _build_select_mock()):
            result = await ensure_unique_agent_slug(db, "My Agent!")

        # base_slug = "my-agent", collision → "my-agent-2"
        self.assertEqual(result, "my-agent-2")


if __name__ == "__main__":
    unittest.main()
