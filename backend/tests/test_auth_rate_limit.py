"""Tests for the login rate limiter in hermeshq.routers.auth."""

import time
import unittest
from collections import defaultdict
from unittest.mock import patch

from fastapi import HTTPException


class TestLoginRateLimit(unittest.TestCase):
    """Test _check_login_rate from hermeshq.routers.auth."""

    def setUp(self) -> None:
        from hermeshq.routers import auth as auth_module
        # Clear the rate limit state before each test
        auth_module._login_attempts.clear()

    def test_under_limit_allows(self) -> None:
        """Less than 10 attempts in window — no exception."""
        from hermeshq.routers.auth import _check_login_rate
        for _ in range(9):
            _check_login_rate("1.2.3.4")
        # 10th should not raise
        _check_login_rate("1.2.3.4")

    def test_at_limit_blocks(self) -> None:
        """Exactly 10 attempts in window — 11th raises HTTP 429."""
        from hermeshq.routers.auth import _check_login_rate, _record_login_attempt
        # Record 10 failed attempts first
        for _ in range(10):
            _record_login_attempt("1.2.3.4")
        # 11th check should raise
        with self.assertRaises(HTTPException) as ctx:
            _check_login_rate("1.2.3.4")
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertIn("Too many", ctx.exception.detail)

    def test_different_ips_independent(self) -> None:
        """Each IP has its own counter."""
        from hermeshq.routers.auth import _check_login_rate, _record_login_attempt
        # Fill up IP 1
        for _ in range(10):
            _record_login_attempt("1.1.1.1")
        # IP 2 should still be allowed
        _check_login_rate("2.2.2.2")
        # IP 1 should be blocked
        with self.assertRaises(HTTPException):
            _check_login_rate("1.1.1.1")

    def test_sliding_window_expiry(self) -> None:
        """Old entries expire, allowing new attempts."""
        from hermeshq.routers.auth import _check_login_rate, _LOGIN_WINDOW_SECONDS
        from hermeshq.routers import auth as auth_module

        # Simulate 10 past attempts at time T
        base_time = 1000.0
        with patch("hermeshq.routers.auth.time.time", return_value=base_time):
            for _ in range(10):
                auth_module._login_attempts["3.3.3.3"].append(base_time)

        # At T + window + 1s, old entries should be evicted
        future_time = base_time + _LOGIN_WINDOW_SECONDS + 1
        with patch("hermeshq.routers.auth.time.time", return_value=future_time):
            # Should NOT raise — old entries expired
            _check_login_rate("3.3.3.3")

    def test_cleanup_old_entries(self) -> None:
        """Old timestamps are pruned during rate-limit check."""
        from hermeshq.routers.auth import _check_login_rate, _record_login_attempt, _LOGIN_WINDOW_SECONDS
        from hermeshq.routers import auth as auth_module

        base_time = 1000.0
        # Simulate an old attempt recorded at base_time
        auth_module._login_attempts["4.4.4.4"].append(base_time)

        # After window expires, the old entry should be pruned by _check_login_rate
        future_time = base_time + _LOGIN_WINDOW_SECONDS + 1
        with patch("hermeshq.routers.auth.time.time", return_value=future_time):
            _check_login_rate("4.4.4.4")  # Prunes old, no new entry added
            # Now record a new attempt — only this one should remain
            _record_login_attempt("4.4.4.4")

        entries = auth_module._login_attempts["4.4.4.4"]
        self.assertEqual(len(entries), 1)

    def test_exact_window_boundary(self) -> None:
        """At exactly the window boundary, old entries are evicted."""
        from hermeshq.routers.auth import _check_login_rate, _LOGIN_WINDOW_SECONDS
        from hermeshq.routers import auth as auth_module

        base_time = 1000.0
        for _ in range(10):
            auth_module._login_attempts["5.5.5.5"].append(base_time)

        # At exactly window boundary: cutoff = now - window = base_time
        # Old entries had t = base_time, and now - t < window is False
        # So old entries are evicted and the new attempt should succeed
        boundary_time = base_time + _LOGIN_WINDOW_SECONDS
        with patch("hermeshq.routers.auth.time.time", return_value=boundary_time):
            _check_login_rate("5.5.5.5")  # Should NOT raise


if __name__ == "__main__":
    unittest.main()
