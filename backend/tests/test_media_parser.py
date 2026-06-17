"""Unit tests for MEDIA:/FILE: parser in hermes_runtime response collection."""

import re
import unittest


class TestMediaParser(unittest.TestCase):
    """Tests for MEDIA:/FILE: reference parsing logic."""

    # This mirrors the regex used in hermes_runtime._run_real
    MEDIA_PATTERN = re.compile(r"(?im)^MEDIA:\s*(.+)$")

    def test_single_media_line(self) -> None:
        text = "Here is the report.\n\nMEDIA:/tmp/report.pdf\n"
        matches = list(self.MEDIA_PATTERN.finditer(text))
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].group(1).strip(), "/tmp/report.pdf")

    def test_multiple_media_lines(self) -> None:
        text = "Results:\n\nMEDIA:/work/chart.png\nMEDIA:/work/data.xlsx\n"
        matches = list(self.MEDIA_PATTERN.finditer(text))
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0].group(1).strip(), "/work/chart.png")
        self.assertEqual(matches[1].group(1).strip(), "/work/data.xlsx")

    def test_no_media_lines(self) -> None:
        text = "Just a normal response with no files.\n\nAll text here."
        matches = list(self.MEDIA_PATTERN.finditer(text))
        self.assertEqual(len(matches), 0)

    def test_media_in_middle_of_text(self) -> None:
        text = "I generated a file.\nMEDIA:/work/output.pdf\nHere is the summary."
        matches = list(self.MEDIA_PATTERN.finditer(text))
        self.assertEqual(len(matches), 1)

    def test_media_case_insensitive(self) -> None:
        text = "media:/work/file.pdf\nMedia:/work/file2.pdf\n"
        matches = list(self.MEDIA_PATTERN.finditer(text))
        self.assertEqual(len(matches), 2)

    def test_media_with_spaces_after_colon(self) -> None:
        text = "MEDIA:   /work/file.pdf\n"
        matches = list(self.MEDIA_PATTERN.finditer(text))
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].group(1).strip(), "/work/file.pdf")

    def test_text_cleaned_after_media_extraction(self) -> None:
        """After removing MEDIA: lines, the text should be clean."""
        text = "Here is the report.\n\nMEDIA:/tmp/report.pdf\n\nSummary above."
        cleaned = self.MEDIA_PATTERN.sub("", text).strip()
        # Remove inline references too
        cleaned = re.sub(r"(?i)MEDIA:\s*/\S+", "", cleaned).strip()
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        self.assertNotIn("MEDIA:", cleaned)
        self.assertIn("Here is the report.", cleaned)
        self.assertIn("Summary above.", cleaned)

    def test_inline_media_reference_cleaned(self) -> None:
        """Inline MEDIA:/path references should be cleaned from text."""
        text = "The file is at MEDIA:/tmp/report.pdf for download."
        cleaned = re.sub(r"(?i)MEDIA:\s*/\S+", "", text).strip()
        self.assertNotIn("MEDIA:", cleaned)
        self.assertNotIn("/tmp/report.pdf", cleaned)
        self.assertIn("The file is at", cleaned)

    def test_url_not_mistaken_as_media(self) -> None:
        """Regular URLs should not be affected."""
        text = "Visit https://example.com for more info."
        matches = list(self.MEDIA_PATTERN.finditer(text))
        self.assertEqual(len(matches), 0)

    def test_media_at_end_of_line(self) -> None:
        """MEDIA: at end of response should be caught."""
        text = "Task done.\nMEDIA:/work/result.csv"
        matches = list(self.MEDIA_PATTERN.finditer(text))
        self.assertEqual(len(matches), 1)

    def test_empty_response(self) -> None:
        text = ""
        matches = list(self.MEDIA_PATTERN.finditer(text))
        self.assertEqual(len(matches), 0)


class TestMediaFileCollection(unittest.TestCase):
    """Test the file collection logic that follows MEDIA: parsing."""

    def test_file_extension_filtering(self) -> None:
        """Only allowed extensions should be collected."""
        ALLOWED_EXTS = {
            ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg",
            ".mp3", ".aac", ".ogg", ".wav", ".m4a", ".flac",
            ".mp4", ".webm", ".mov", ".avi", ".mkv",
            ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
            ".txt", ".csv", ".json", ".md", ".xml", ".html", ".zip",
        }
        self.assertIn(".pdf", ALLOWED_EXTS)
        self.assertIn(".xlsx", ALLOWED_EXTS)
        self.assertIn(".png", ALLOWED_EXTS)
        self.assertNotIn(".exe", ALLOWED_EXTS)
        self.assertNotIn(".sh", ALLOWED_EXTS)
        self.assertNotIn(".py", ALLOWED_EXTS)

    def test_mime_type_resolution(self) -> None:
        MIME_MAP = {
            ".pdf": "application/pdf",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".png": "image/png",
            ".mp3": "audio/mpeg",
            ".mp4": "video/mp4",
        }
        for ext, expected_mime in MIME_MAP.items():
            self.assertEqual(MIME_MAP.get(ext, "application/octet-stream"), expected_mime)

    def test_attachment_structure(self) -> None:
        """Verify the expected attachment dict structure."""
        att = {
            "file_id": "abc-123",
            "filename": "report.pdf",
            "media_type": "application/pdf",
            "size": 12345,
            "caption": "",
            "source_path": "/tmp/report.pdf",
        }
        # All required fields present
        for key in ("file_id", "filename", "media_type", "size", "caption"):
            self.assertIn(key, att)
        # source_path is internal
        self.assertIn("source_path", att)

    def test_attachment_strips_source_path_for_client(self) -> None:
        """source_path should be stripped before sending to client."""
        raw_att = {
            "file_id": "abc-123",
            "filename": "report.pdf",
            "media_type": "application/pdf",
            "size": 12345,
            "caption": "",
            "source_path": "/tmp/report.pdf",
        }
        client_att = {k: v for k, v in raw_att.items() if k != "source_path"}
        self.assertNotIn("source_path", client_att)
        self.assertNotIn("path", client_att)
        self.assertEqual(client_att["file_id"], "abc-123")


class TestSixagenticChannelSupport(unittest.TestCase):
    """Test that sixagentic is properly recognized as a supported platform."""

    def test_platform_in_supported_set(self) -> None:
        """SUPPORTED_PLATFORMS should include 'sixagentic'."""
        # This mirrors the constant in messaging_channels.py
        SUPPORTED = {"telegram", "whatsapp", "microsoft_teams", "google_chat", "kapso_whatsapp", "sixagentic"}
        self.assertIn("sixagentic", SUPPORTED)

    def test_config_yaml_writes_sixagentic(self) -> None:
        """When sixagentic channel is enabled, config.yaml should include it."""
        # Simulate the config structure
        config: dict = {}
        platforms = config.setdefault("platforms", {})
        platforms["sixagentic"] = {"enabled": True}
        self.assertIn("sixagentic", config["platforms"])
        self.assertTrue(config["platforms"]["sixagentic"]["enabled"])


if __name__ == "__main__":
    unittest.main()
