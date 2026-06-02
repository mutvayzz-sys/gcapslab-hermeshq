"""Unit tests for hermeshq.versioning module."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hermeshq.versioning import get_app_version


class TestGetAppVersion(unittest.TestCase):
    """Tests for get_app_version()."""

    def setUp(self):
        get_app_version.cache_clear()

    def tearDown(self):
        get_app_version.cache_clear()

    def test_reads_version_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            version_file = Path(tmpdir) / "VERSION"
            version_file.write_text("1.2.3", encoding="utf-8")
            with patch("hermeshq.versioning.VERSION_FILE", version_file):
                get_app_version.cache_clear()
                self.assertEqual(get_app_version(), "1.2.3")

    def test_strips_whitespace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            version_file = Path(tmpdir) / "VERSION"
            version_file.write_text("  2.0.0\n  ", encoding="utf-8")
            with patch("hermeshq.versioning.VERSION_FILE", version_file):
                get_app_version.cache_clear()
                self.assertEqual(get_app_version(), "2.0.0")

    def test_empty_file_returns_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            version_file = Path(tmpdir) / "VERSION"
            version_file.write_text("", encoding="utf-8")
            with patch("hermeshq.versioning.VERSION_FILE", version_file):
                get_app_version.cache_clear()
                self.assertEqual(get_app_version(), "0.0.0")

    def test_whitespace_only_returns_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            version_file = Path(tmpdir) / "VERSION"
            version_file.write_text("   \n  ", encoding="utf-8")
            with patch("hermeshq.versioning.VERSION_FILE", version_file):
                get_app_version.cache_clear()
                self.assertEqual(get_app_version(), "0.0.0")

    def test_missing_file_returns_default(self):
        version_file = Path("/nonexistent/path/VERSION")
        with patch("hermeshq.versioning.VERSION_FILE", version_file):
            get_app_version.cache_clear()
            self.assertEqual(get_app_version(), "0.0.0")

    def test_returns_string(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            version_file = Path(tmpdir) / "VERSION"
            version_file.write_text("1.0.0", encoding="utf-8")
            with patch("hermeshq.versioning.VERSION_FILE", version_file):
                get_app_version.cache_clear()
                self.assertIsInstance(get_app_version(), str)


if __name__ == "__main__":
    unittest.main()
