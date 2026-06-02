"""Tests for the login rate limiter in hermeshq.routers.auth."""

import time
import unittest
from collections import defaultdict
from unittest.mock import patch

from fastapi import HTTPException


class TestLoginRateLimit(unittest.TestCase):
    """Test _check_login_rate_limit from hermeshq.routers.auth."""

    def setUp(self) -> None:
        from hermeshq.routers import auth as auth_module
        # Clear the rate limit state before each test
        auth_module._LOGIN_RATE_LIMITS.clear()

    def test_under_limit_allows(self) -> None:
        """Less than 10 attempts in 60s window — no exception."""
        from hermeshq.routers.auth import _check_login_rate_limit
        for _ in range(9):
            _check_login_rate_limit("1.2.3.4")
        # 9th should not raise
        _check_login_rate_limit("1.2.3.4")

    def test_at_limit_blocks(self) -> None:
        """Exactly 10 attempts in window — 11th raises HTTP 429."""
        from hermeshq.routers.auth import _check_login_rate_limit
        for _ in range(10):
            _check_login_rate_limit("1.2.3.4")
        with self.assertRaises(HTTPException) as ctx:
            _check_login_rate_limit("1.2.3.4")
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertIn("Too many", ctx.exception.detail)

    def test_different_ips_independent(self) -> None:
        """Each IP has its own counter."""
        from hermeshq.routers.auth import _check_login_rate_limit
        # Fill up IP 1
        for _ in range(10):
            _check_login_rate_limit("1.1.1.1")
        # IP 2 should still be allowed
        _check_login_rate_limit("2.2.2.2")
        # IP 1 should be blocked
        with self.assertRaises(HTTPException):
            _check_login_rate_limit("1.1.1.1")

    def test_sliding_window_expiry(self) -> None:
        """Old entries expire, allowing new attempts."""
        from hermeshq.routers.auth import _check_login_rate_limit, _LOGIN_WINDOW_SECONDS
        from hermeshq.routers import auth as auth_module

        # Simulate 10 past attempts at time T
        base_time = 1000.0
        with patch("hermeshq.routers.auth.time.monotonic", return_value=base_time):
            for _ in range(10):
                _check_login_rate_limit("3.3.3.3")

        # At T + 61s, old entries should be evicted
        future_time = base_time + _LOGIN_WINDOW_SECONDS + 1
        with patch("hermeshq.routers.auth.time.monotonic", return_value=future_time):
            # Should NOT raise — old entries expired
            _check_login_rate_limit("3.3.3.3")

    def test_cleanup_old_entries(self) -> None:
        """Old timestamps are removed from the list."""
        from hermeshq.routers.auth import _check_login_rate_limit, _LOGIN_WINDOW_SECONDS
        from hermeshq.routers import auth as auth_module

        base_time = 1000.0
        with patch("hermeshq.routers.auth.time.monotonic", return_value=base_time):
            _check_login_rate_limit("4.4.4.4")

        # After window expires, the list should be cleaned
        future_time = base_time + _LOGIN_WINDOW_SECONDS + 1
        with patch("hermeshq.routers.auth.time.monotonic", return_value=future_time):
            _check_login_rate_limit("4.4.4.4")

        # Only the new entry should remain (the old one was evicted)
        entries = auth_module._LOGIN_RATE_LIMITS["4.4.4.4"]
        self.assertEqual(len(entries), 1)

    def test_exact_window_boundary(self) -> None:
        """At exactly the window boundary, old entries are evicted (t > cutoff is strict)."""
        from hermeshq.routers.auth import _check_login_rate_limit, _LOGIN_WINDOW_SECONDS
        from hermeshq.routers import auth as auth_module

        base_time = 1000.0
        with patch("hermeshq.routers.auth.time.monotonic", return_value=base_time):
            for _ in range(10):
                _check_login_rate_limit("5.5.5.5")

        # At exactly window boundary: cutoff = now - window = base_time
        # Old entries had t = base_time, and t > cutoff means base_time > base_time → False
        # So old entries are evicted and the new attempt should succeed (no exception)
        boundary_time = base_time + _LOGIN_WINDOW_SECONDS
        with patch("hermeshq.routers.auth.time.monotonic", return_value=boundary_time):
            _check_login_rate_limit("5.5.5.5")  # Should NOT raise


if __name__ == "__main__":
    unittest.main()
