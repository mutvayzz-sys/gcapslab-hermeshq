"""
Regression tests for the HermesHQ Backend Crash Loop bug.

Bug: When an agent with a Telegram channel fails bootstrap (timeout, InvalidToken, etc.),
the backend enters an infinite crash loop, making ALL agents inaccessible.

Root causes fixed:
  A. Generic `except Exception` set `transient=False` — now uses `transient=True`.
  B. No global try/except in `bootstrap_gateways()` — now wraps inner method.
  C. No filter on `Agent.status` — now excludes stopped/archived agents.
  D. Hard-coded timeout/retry values — now configurable via env vars.

Reference: HermesHQ v2026.5.19.2 crash loop incident (2026-05-26)
"""

import asyncio
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from hermeshq.services.gateway_supervisor import (
    BOOTSTRAP_CHANNEL_TIMEOUT_SECONDS,
    BOOTSTRAP_RETRY_ATTEMPTS,
    GatewaySupervisor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(
    agent_id: str = "agent-001",
    name: str = "TestAgent",
    status: str = "running",
    is_archived: bool = False,
) -> Mock:
    agent = Mock()
    agent.id = agent_id
    agent.name = name
    agent.status = status
    agent.is_archived = is_archived
    agent.node_id = "node-1"
    agent.workspace_path = f"/tmp/workspaces/{agent_id}"
    return agent


def _make_channel(
    agent_id: str = "agent-001",
    platform: str = "telegram",
    enabled: bool = True,
    secret_ref: str = "tg-bot-token",
    metadata_json: dict | None = None,
) -> Mock:
    channel = Mock()
    channel.id = f"ch-{agent_id}-{platform}"
    channel.agent_id = agent_id
    channel.platform = platform
    channel.enabled = enabled
    channel.secret_ref = secret_ref
    channel.status = "stopped"
    channel.last_error = None
    channel.metadata_json = metadata_json if metadata_json is not None else {}
    channel.mode = "bidirectional"
    channel.allowed_user_ids = []
    channel.home_chat_id = None
    channel.home_chat_name = None
    channel.require_mention = False
    channel.free_response_chat_ids = []
    channel.unauthorized_dm_behavior = "pair"
    return channel


def _make_supervisor() -> tuple[GatewaySupervisor, MagicMock, Mock, Mock]:
    session_factory = MagicMock()
    event_broker = Mock()
    installation_manager = Mock()
    supervisor = GatewaySupervisor(session_factory, event_broker, installation_manager)
    return supervisor, session_factory, event_broker, installation_manager


def _make_session(
    rows=None,
    channel_for_get=None,
    agent_for_get=None,
) -> MagicMock:
    """
    Build a mock async session using MagicMock (not AsyncMock!) so that
    synchronous attribute access (e.g., result.all()) returns plain values.

    Parameters:
        rows: list of (channel, agent) tuples for the bootstrap query's .all()
        channel_for_get: channel returned by _get_channel (scalar_one_or_none)
        agent_for_get: agent returned by session.get(Agent, pk)
    """
    s = MagicMock()
    s.__aenter__ = AsyncMock(return_value=s)
    s.__aexit__ = AsyncMock(return_value=False)
    s.commit = AsyncMock()

    # session.execute() returns a result object
    mock_result = Mock()
    mock_result.all = Mock(return_value=rows if rows is not None else [])
    mock_result.scalar_one_or_none = Mock(return_value=channel_for_get)
    s.execute = AsyncMock(return_value=mock_result)

    # session.get(Model, pk)
    s.get = AsyncMock(return_value=agent_for_get)

    return s


class SessionSequence:
    """Callable that returns sessions in order from a list."""

    def __init__(self, *sessions):
        self.sessions = list(sessions)
        self.idx = 0

    def __call__(self, *args, **kwargs):
        s = self.sessions[min(self.idx, len(self.sessions) - 1)]
        self.idx += 1
        return s


# ---------------------------------------------------------------------------
# Test: Fix B — Global try/except in bootstrap_gateways()
# ---------------------------------------------------------------------------

class TestBootstrapGlobalSafetyNet(unittest.IsolatedAsyncioTestCase):
    """
    Verify that bootstrap_gateways() NEVER propagates exceptions to the caller.
    This is the most critical fix: even if _do_bootstrap_gateways() fails in
    completely unexpected ways, uvicorn must keep running.
    """

    async def test_catches_runtime_error(self) -> None:
        supervisor, _, _, _ = _make_supervisor()
        supervisor._do_bootstrap_gateways = AsyncMock(side_effect=RuntimeError("DB exploded"))
        await supervisor.bootstrap_gateways()

    async def test_catches_database_connection_error(self) -> None:
        supervisor, session_factory, _, _ = _make_supervisor()
        broken = MagicMock()
        broken.__aenter__ = AsyncMock(side_effect=ConnectionError("PostgreSQL is down"))
        broken.__aexit__ = AsyncMock(return_value=False)
        session_factory.return_value = broken
        await supervisor.bootstrap_gateways()

    async def test_catches_type_error(self) -> None:
        supervisor, _, _, _ = _make_supervisor()
        supervisor._do_bootstrap_gateways = AsyncMock(side_effect=TypeError("unexpected"))
        await supervisor.bootstrap_gateways()

    async def test_catches_key_error(self) -> None:
        supervisor, _, _, _ = _make_supervisor()
        supervisor._do_bootstrap_gateways = AsyncMock(side_effect=KeyError("missing"))
        await supervisor.bootstrap_gateways()

    async def test_catches_import_error(self) -> None:
        supervisor, _, _, _ = _make_supervisor()
        supervisor._do_bootstrap_gateways = AsyncMock(side_effect=ImportError("no module"))
        await supervisor.bootstrap_gateways()

    async def test_logs_critical_on_failure(self) -> None:
        supervisor, _, _, _ = _make_supervisor()
        supervisor._do_bootstrap_gateways = AsyncMock(side_effect=RuntimeError("test"))
        with patch("hermeshq.services.gateway_supervisor.logger") as mock_logger:
            await supervisor.bootstrap_gateways()
            mock_logger.exception.assert_called_once()
            self.assertIn("Fatal error", mock_logger.exception.call_args[0][0])


# ---------------------------------------------------------------------------
# Test: Fix C — Agent status filtering
# ---------------------------------------------------------------------------

class TestBootstrapAgentStatusFilter(unittest.IsolatedAsyncioTestCase):
    """
    Verify that stopped and archived agents are excluded from bootstrap targets.
    """

    async def test_stopped_agents_excluded(self) -> None:
        """Only the running agent's channel should be bootstrapped."""
        supervisor, sf, _, _ = _make_supervisor()
        running = _make_agent(agent_id="run-1", status="running")
        ch_run = _make_channel(agent_id="run-1")

        sf.side_effect = SessionSequence(
            _make_session(rows=[(ch_run, running)]),  # bootstrap query
            _make_session(channel_for_get=ch_run),     # success path
        )
        supervisor.start_channel = AsyncMock()

        await supervisor._do_bootstrap_gateways()

        self.assertEqual(supervisor.start_channel.call_count, 1)
        self.assertEqual(supervisor.start_channel.call_args[0][0].id, "run-1")

    async def test_archived_agents_excluded(self) -> None:
        supervisor, sf, _, _ = _make_supervisor()
        sf.side_effect = SessionSequence(_make_session(rows=[]))
        supervisor.start_channel = AsyncMock()

        await supervisor._do_bootstrap_gateways()
        supervisor.start_channel.assert_not_called()

    async def test_archived_status_excluded(self) -> None:
        supervisor, sf, _, _ = _make_supervisor()
        sf.side_effect = SessionSequence(_make_session(rows=[]))
        supervisor.start_channel = AsyncMock()

        await supervisor._do_bootstrap_gateways()
        supervisor.start_channel.assert_not_called()

    async def test_multiple_running_agents_bootstrapped(self) -> None:
        supervisor, sf, _, _ = _make_supervisor()
        a1 = _make_agent(agent_id="r1", status="running")
        a2 = _make_agent(agent_id="r2", status="running")
        c1 = _make_channel(agent_id="r1")
        c2 = _make_channel(agent_id="r2")

        sf.side_effect = SessionSequence(
            _make_session(rows=[(c1, a1), (c2, a2)]),
            _make_session(channel_for_get=c1),
            _make_session(channel_for_get=c2),
        )
        supervisor.start_channel = AsyncMock()

        await supervisor._do_bootstrap_gateways()
        self.assertEqual(supervisor.start_channel.call_count, 2)

    async def test_all_stopped_means_no_bootstrap(self) -> None:
        supervisor, sf, _, _ = _make_supervisor()
        sf.side_effect = SessionSequence(_make_session(rows=[]))
        supervisor.start_channel = AsyncMock()

        await supervisor._do_bootstrap_gateways()
        supervisor.start_channel.assert_not_called()

    async def test_runtime_disabled_channels_skipped(self) -> None:
        supervisor, sf, _, _ = _make_supervisor()
        agent = _make_agent(agent_id="rd-1", status="running")
        ch = _make_channel(agent_id="rd-1", metadata_json={"runtime_disabled": True})

        sf.side_effect = SessionSequence(_make_session(rows=[(ch, agent)]))
        supervisor.start_channel = AsyncMock()

        await supervisor._do_bootstrap_gateways()
        supervisor.start_channel.assert_not_called()


# ---------------------------------------------------------------------------
# Test: Fix A — Generic Exception handler uses transient=True
# ---------------------------------------------------------------------------

class TestBootstrapTransientHandling(unittest.IsolatedAsyncioTestCase):
    """
    Verify that unexpected exceptions are treated as transient and retried.
    """

    async def test_invalid_token_retried(self) -> None:
        """InvalidToken from Fernet should be caught and retried."""
        supervisor, sf, _, _ = _make_supervisor()
        agent = _make_agent(agent_id="brk-1", name="BrokenTg")
        channel = _make_channel(agent_id="brk-1", platform="telegram")

        # Bootstrap query + error sessions for each retry
        sessions = [_make_session(rows=[(channel, agent)])]
        for _ in range(BOOTSTRAP_RETRY_ATTEMPTS):
            sessions.append(_make_session(
                channel_for_get=channel,
                agent_for_get=agent,
            ))
        sf.side_effect = SessionSequence(*sessions)

        from cryptography.fernet import InvalidToken
        supervisor.start_channel = AsyncMock(side_effect=InvalidToken)

        await supervisor._do_bootstrap_gateways()
        self.assertEqual(supervisor.start_channel.call_count, BOOTSTRAP_RETRY_ATTEMPTS)

    async def test_one_failing_agent_does_not_block_others(self) -> None:
        """If one agent fails, others should still bootstrap."""
        supervisor, sf, _, _ = _make_supervisor()
        bad = _make_agent(agent_id="bad-1", name="Bad")
        good = _make_agent(agent_id="good-1", name="Good")
        ch_bad = _make_channel(agent_id="bad-1")
        ch_good = _make_channel(agent_id="good-1")

        sessions = [_make_session(rows=[(ch_bad, bad), (ch_good, good)])]
        # Error sessions for bad agent retries
        for _ in range(BOOTSTRAP_RETRY_ATTEMPTS):
            sessions.append(_make_session(
                channel_for_get=ch_bad,
                agent_for_get=bad,
            ))
        # Success session for good agent
        sessions.append(_make_session(channel_for_get=ch_good))
        sf.side_effect = SessionSequence(*sessions)

        started: list[str] = []

        async def start_fn(agent_obj, platform):
            if agent_obj.id == "bad-1":
                raise RuntimeError("Simulated InvalidToken")
            started.append(agent_obj.id)

        supervisor.start_channel = start_fn

        await supervisor._do_bootstrap_gateways()
        self.assertIn("good-1", started)

    async def test_runtime_error_retried(self) -> None:
        """Generic RuntimeError should be retried BOOTSTRAP_RETRY_ATTEMPTS times."""
        supervisor, sf, _, _ = _make_supervisor()
        agent = _make_agent(agent_id="retry-1")
        channel = _make_channel(agent_id="retry-1")

        sessions = [_make_session(rows=[(channel, agent)])]
        for _ in range(BOOTSTRAP_RETRY_ATTEMPTS):
            sessions.append(_make_session(
                channel_for_get=channel,
                agent_for_get=agent,
            ))
        sf.side_effect = SessionSequence(*sessions)

        attempts = 0

        async def fail(agent_obj, platform):
            nonlocal attempts
            attempts += 1
            raise RuntimeError("Transient failure")

        supervisor.start_channel = fail

        await supervisor._do_bootstrap_gateways()
        self.assertEqual(attempts, BOOTSTRAP_RETRY_ATTEMPTS)


# ---------------------------------------------------------------------------
# Test: Fix D — Configurable timeout and retries
# ---------------------------------------------------------------------------

class TestConfigurableBootstrapParameters(unittest.TestCase):
    def test_default_timeout_reasonable(self) -> None:
        self.assertLessEqual(BOOTSTRAP_CHANNEL_TIMEOUT_SECONDS, 120)

    def test_default_retries_reasonable(self) -> None:
        self.assertLessEqual(BOOTSTRAP_RETRY_ATTEMPTS, 3)

    def test_env_timeout(self) -> None:
        with patch.dict(os.environ, {"HQ_BOOTSTRAP_TIMEOUT": "45"}):
            self.assertEqual(int(os.getenv("HQ_BOOTSTRAP_TIMEOUT", "30")), 45)

    def test_env_retries(self) -> None:
        with patch.dict(os.environ, {"HQ_BOOTSTRAP_RETRIES": "1"}):
            self.assertEqual(int(os.getenv("HQ_BOOTSTRAP_RETRIES", "2")), 1)

    def test_defaults_without_env(self) -> None:
        env = {k: v for k, v in os.environ.items()
               if k not in ("HQ_BOOTSTRAP_TIMEOUT", "HQ_BOOTSTRAP_RETRIES")}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(int(os.getenv("HQ_BOOTSTRAP_TIMEOUT", "30")), 30)
            self.assertEqual(int(os.getenv("HQ_BOOTSTRAP_RETRIES", "2")), 2)


# ---------------------------------------------------------------------------
# Test: _is_transient_bootstrap_error helper
# ---------------------------------------------------------------------------

class TestIsTransientBootstrapError(unittest.TestCase):
    def setUp(self) -> None:
        self.supervisor, _, _, _ = _make_supervisor()

    def test_timeout(self) -> None:
        self.assertTrue(self.supervisor._is_transient_bootstrap_error("timed out after 120s"))

    def test_pid_race(self) -> None:
        self.assertTrue(self.supervisor._is_transient_bootstrap_error("PID file race lost"))

    def test_resource_busy(self) -> None:
        self.assertTrue(self.supervisor._is_transient_bootstrap_error("resource busy"))

    def test_already_running(self) -> None:
        self.assertTrue(self.supervisor._is_transient_bootstrap_error("already running"))

    def test_invalid_token_not_transient_by_keyword(self) -> None:
        self.assertFalse(self.supervisor._is_transient_bootstrap_error("InvalidToken"))

    def test_empty(self) -> None:
        self.assertFalse(self.supervisor._is_transient_bootstrap_error(""))

    def test_none(self) -> None:
        self.assertFalse(self.supervisor._is_transient_bootstrap_error(None))


# ---------------------------------------------------------------------------
# Test: Enterprise platform exclusion
# ---------------------------------------------------------------------------

class TestEnterprisePlatformExclusion(unittest.IsolatedAsyncioTestCase):
    async def test_google_chat_skipped(self) -> None:
        supervisor, sf, _, _ = _make_supervisor()
        agent = _make_agent(agent_id="gc-1")
        ch = _make_channel(agent_id="gc-1", platform="google_chat")

        sf.side_effect = SessionSequence(_make_session(rows=[(ch, agent)]))
        supervisor.start_channel = AsyncMock()

        await supervisor._do_bootstrap_gateways()
        supervisor.start_channel.assert_not_called()

    async def test_kapso_whatsapp_skipped(self) -> None:
        supervisor, sf, _, _ = _make_supervisor()
        agent = _make_agent(agent_id="kw-1")
        ch = _make_channel(agent_id="kw-1", platform="kapso_whatsapp")

        sf.side_effect = SessionSequence(_make_session(rows=[(ch, agent)]))
        supervisor.start_channel = AsyncMock()

        await supervisor._do_bootstrap_gateways()
        supervisor.start_channel.assert_not_called()


# ---------------------------------------------------------------------------
# Test: No-target scenarios
# ---------------------------------------------------------------------------

class TestBootstrapNoTargets(unittest.IsolatedAsyncioTestCase):
    async def test_empty_channels(self) -> None:
        supervisor, sf, _, _ = _make_supervisor()
        sf.side_effect = SessionSequence(_make_session(rows=[]))
        supervisor.start_channel = AsyncMock()

        await supervisor._do_bootstrap_gateways()
        supervisor.start_channel.assert_not_called()

    async def test_all_disabled(self) -> None:
        supervisor, sf, _, _ = _make_supervisor()
        sf.side_effect = SessionSequence(_make_session(rows=[]))
        supervisor.start_channel = AsyncMock()

        await supervisor._do_bootstrap_gateways()
        supervisor.start_channel.assert_not_called()


# ---------------------------------------------------------------------------
# Test: Bootstrap state tracking
# ---------------------------------------------------------------------------

class TestBootstrapStateTracking(unittest.TestCase):
    def setUp(self) -> None:
        self.supervisor, _, _, _ = _make_supervisor()

    def test_success_state(self) -> None:
        ch = _make_channel()
        now = datetime.now(timezone.utc)
        self.supervisor._mark_bootstrap_state(ch, status="success", attempted_at=now, duration_ms=1500, attempts=1)
        b = ch.metadata_json["bootstrap"]
        self.assertEqual(b["last_status"], "success")
        self.assertEqual(b["last_duration_ms"], 1500)
        self.assertEqual(b["last_attempts"], 1)
        self.assertEqual(b["last_success_at"], now.isoformat())

    def test_failure_state(self) -> None:
        ch = _make_channel()
        now = datetime.now(timezone.utc)
        self.supervisor._mark_bootstrap_state(ch, status="failed", attempted_at=now, error="InvalidToken", attempts=3)
        b = ch.metadata_json["bootstrap"]
        self.assertEqual(b["last_status"], "failed")
        self.assertEqual(b["last_error"], "InvalidToken")
        self.assertIsNone(b["last_success_at"])

    def test_preserves_previous_success(self) -> None:
        ch = _make_channel()
        t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.supervisor._mark_bootstrap_state(ch, status="success", attempted_at=t1, duration_ms=500, attempts=1)
        t2 = datetime(2026, 5, 26, tzinfo=timezone.utc)
        self.supervisor._mark_bootstrap_state(ch, status="failed", attempted_at=t2, error="timeout", attempts=2)
        b = ch.metadata_json["bootstrap"]
        self.assertEqual(b["last_status"], "failed")
        self.assertEqual(b["last_success_at"], t1.isoformat())


# ---------------------------------------------------------------------------
# Test: _channel_runtime_enabled helper
# ---------------------------------------------------------------------------

class TestChannelRuntimeEnabled(unittest.TestCase):
    def setUp(self) -> None:
        self.supervisor, _, _, _ = _make_supervisor()

    def test_enabled(self) -> None:
        self.assertTrue(self.supervisor._channel_runtime_enabled(_make_channel(enabled=True)))

    def test_disabled(self) -> None:
        self.assertFalse(self.supervisor._channel_runtime_enabled(_make_channel(enabled=False)))

    def test_runtime_disabled(self) -> None:
        ch = _make_channel(enabled=True, metadata_json={"runtime_disabled": True})
        self.assertFalse(self.supervisor._channel_runtime_enabled(ch))

    def test_runtime_disabled_false(self) -> None:
        ch = _make_channel(enabled=True, metadata_json={"runtime_disabled": False})
        self.assertTrue(self.supervisor._channel_runtime_enabled(ch))


# ---------------------------------------------------------------------------
# Test: Timeout behavior
# ---------------------------------------------------------------------------

class TestBootstrapTimeoutBehavior(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_retried(self) -> None:
        supervisor, sf, _, _ = _make_supervisor()
        agent = _make_agent(agent_id="tout-1")
        channel = _make_channel(agent_id="tout-1")

        sessions = [_make_session(rows=[(channel, agent)])]
        for _ in range(BOOTSTRAP_RETRY_ATTEMPTS):
            sessions.append(_make_session(
                channel_for_get=channel,
                agent_for_get=agent,
            ))
        sf.side_effect = SessionSequence(*sessions)

        attempts = 0
        async def timeout_fn(a, p):
            nonlocal attempts
            attempts += 1
            raise asyncio.TimeoutError()

        supervisor.start_channel = timeout_fn

        await supervisor._do_bootstrap_gateways()
        self.assertEqual(attempts, BOOTSTRAP_RETRY_ATTEMPTS)

    async def test_timeout_does_not_crash_backend(self) -> None:
        supervisor, sf, _, _ = _make_supervisor()
        agent = _make_agent(agent_id="tout-2")
        channel = _make_channel(agent_id="tout-2")

        sessions = [_make_session(rows=[(channel, agent)])]
        for _ in range(BOOTSTRAP_RETRY_ATTEMPTS):
            sessions.append(_make_session(
                channel_for_get=channel,
                agent_for_get=agent,
            ))
        sf.side_effect = SessionSequence(*sessions)
        supervisor.start_channel = AsyncMock(side_effect=asyncio.TimeoutError())

        # Outer method must not raise
        await supervisor.bootstrap_gateways()


# ---------------------------------------------------------------------------
# Test: End-to-end scenario from the bug report
# ---------------------------------------------------------------------------

class TestCrashLoopScenario(unittest.IsolatedAsyncioTestCase):
    """
    Reproduce the exact scenario from the bug report:
    stopped + broken agents should not crash the backend.
    """

    async def test_stopped_agents_filtered_out(self) -> None:
        """2 stopped agents + 3 running — only running ones bootstrap."""
        supervisor, sf, _, _ = _make_supervisor()
        workers = [
            _make_agent(agent_id="w1", name="Claw-Master", status="running"),
            _make_agent(agent_id="w2", name="Agente-Hector", status="running"),
            _make_agent(agent_id="w3", name="Agente-Joel", status="running"),
        ]
        channels = [_make_channel(agent_id=a.id) for a in workers]

        # SQL filter removes stopped agents
        sessions = [_make_session(rows=list(zip(channels, workers)))]
        for ch in channels:
            sessions.append(_make_session(channel_for_get=ch))
        sf.side_effect = SessionSequence(*sessions)
        supervisor.start_channel = AsyncMock()

        await supervisor.bootstrap_gateways()
        self.assertEqual(supervisor.start_channel.call_count, 3)

    async def test_broken_agent_if_leaked_does_not_crash(self) -> None:
        """Even if a stopped agent leaks through, InvalidToken doesn't crash."""
        supervisor, sf, _, _ = _make_supervisor()
        agent = _make_agent(agent_id="leak-1", name="Leaked-Broken")
        channel = _make_channel(agent_id="leak-1", platform="telegram")

        sessions = [_make_session(rows=[(channel, agent)])]
        for _ in range(BOOTSTRAP_RETRY_ATTEMPTS):
            sessions.append(_make_session(
                channel_for_get=channel,
                agent_for_get=agent,
            ))
        sf.side_effect = SessionSequence(*sessions)

        from cryptography.fernet import InvalidToken
        supervisor.start_channel = AsyncMock(side_effect=InvalidToken)

        await supervisor.bootstrap_gateways()
        self.assertEqual(supervisor.start_channel.call_count, BOOTSTRAP_RETRY_ATTEMPTS)

    async def test_recovery_after_transient_error(self) -> None:
        """Agent that fails once then succeeds should end up running."""
        supervisor, sf, _, _ = _make_supervisor()
        agent = _make_agent(agent_id="recover-1")
        channel = _make_channel(agent_id="recover-1")

        sessions = [
            _make_session(rows=[(channel, agent)]),       # bootstrap query
            _make_session(                                  # error session (1st attempt)
                channel_for_get=channel,
                agent_for_get=agent,
            ),
            _make_session(channel_for_get=channel),        # success session (2nd attempt)
        ]
        sf.side_effect = SessionSequence(*sessions)

        calls = 0
        async def start_fn(a, p):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise asyncio.TimeoutError()

        supervisor.start_channel = start_fn

        await supervisor._do_bootstrap_gateways()
        self.assertEqual(calls, 2)


if __name__ == "__main__":
    unittest.main()
