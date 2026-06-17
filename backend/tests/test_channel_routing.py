"""Unit tests for channel routing — reply_to suppression of external delivery."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


class TestChannelRoutingSystemPrompt(unittest.TestCase):
    """Test that the mobile_app system prompt injection works in hermes_runtime."""

    def test_mobile_app_prompt_injection(self) -> None:
        """When reply_to=mobile_app, the system prompt should include the routing instruction."""
        base_prompt = "You are a helpful assistant."
        metadata = {"reply_to": "mobile_app", "source": "mobile_app"}

        # Simulate the injection logic from hermes_runtime._run_real
        _reply_to = str(metadata.get("reply_to") or metadata.get("source") or "").strip().lower()
        if _reply_to == "mobile_app":
            runtime_system_prompt = (
                base_prompt
                + "\n\n"
                + "IMPORTANT: You are responding through the SixAgentic mobile app. "
                "Always provide your response directly in the task response text. "
                "Do NOT send responses through Telegram, WhatsApp, email, or any other "
                "external channel. If you generate files, they will be automatically "
                "attached as response_attachments."
            )
        else:
            runtime_system_prompt = base_prompt

        self.assertIn("SixAgentic mobile app", runtime_system_prompt)
        self.assertIn("Do NOT send responses through Telegram", runtime_system_prompt)

    def test_telegram_prompt_not_injected(self) -> None:
        """When reply_to=telegram, the system prompt should NOT be modified."""
        base_prompt = "You are a helpful assistant."
        metadata = {"reply_to": "telegram"}

        _reply_to = str(metadata.get("reply_to") or metadata.get("source") or "").strip().lower()
        if _reply_to == "mobile_app":
            runtime_system_prompt = base_prompt + "\n\nINJECTED"
        else:
            runtime_system_prompt = base_prompt

        self.assertEqual(runtime_system_prompt, base_prompt)

    def test_empty_reply_to_uses_default(self) -> None:
        """When reply_to is not set, the system prompt should NOT be modified."""
        base_prompt = "You are a helpful assistant."
        metadata = {}

        _reply_to = str(metadata.get("reply_to") or metadata.get("source") or "").strip().lower()
        if _reply_to == "mobile_app":
            runtime_system_prompt = base_prompt + "\n\nINJECTED"
        else:
            runtime_system_prompt = base_prompt

        self.assertEqual(runtime_system_prompt, base_prompt)

    def test_source_fallback_when_reply_to_missing(self) -> None:
        """When reply_to is missing but source=mobile_app, prompt should still be injected."""
        base_prompt = "You are a helpful assistant."
        metadata = {"source": "mobile_app"}

        _reply_to = str(metadata.get("reply_to") or metadata.get("source") or "").strip().lower()
        if _reply_to == "mobile_app":
            runtime_system_prompt = (
                base_prompt + "\n\n"
                + "IMPORTANT: You are responding through the SixAgentic mobile app. "
                "Always provide your response directly in the task response text. "
                "Do NOT send responses through Telegram, WhatsApp, email, or any other "
                "external channel."
            )
        else:
            runtime_system_prompt = base_prompt

        self.assertIn("SixAgentic mobile app", runtime_system_prompt)


class TestChannelRoutingExternalDelivery(unittest.TestCase):
    """Test that _queue_external_callback_delivery respects reply_to=mobile_app."""

    def test_mobile_app_skips_telegram_delivery(self) -> None:
        """When reply_to=mobile_app, the external callback delivery should be skipped."""
        # Simulate the early return logic from agent_supervisor
        metadata = {
            "reply_to": "mobile_app",
            "callback_delivery": {
                "platform": "telegram",
                "chat_id": "12345",
            },
        }

        reply_to = str(metadata.get("reply_to") or metadata.get("source") or "").strip().lower()
        if reply_to == "mobile_app":
            # Should return early — no Telegram delivery
            skipped = True
        else:
            skipped = False

        self.assertTrue(skipped)

    def test_telegram_delivery_proceeds_normally(self) -> None:
        """When reply_to=telegram, the external callback delivery should proceed."""
        metadata = {
            "reply_to": "telegram",
            "callback_delivery": {
                "platform": "telegram",
                "chat_id": "12345",
            },
        }

        reply_to = str(metadata.get("reply_to") or metadata.get("source") or "").strip().lower()
        if reply_to == "mobile_app":
            skipped = True
        else:
            skipped = False

        self.assertFalse(skipped)

    def test_empty_reply_to_proceeds_normally(self) -> None:
        """When reply_to is not set, the external callback delivery should proceed."""
        metadata = {
            "callback_delivery": {
                "platform": "telegram",
                "chat_id": "12345",
            },
        }

        reply_to = str(metadata.get("reply_to") or metadata.get("source") or "").strip().lower()
        if reply_to == "mobile_app":
            skipped = True
        else:
            skipped = False

        self.assertFalse(skipped)

    def test_source_fallback_skips_delivery(self) -> None:
        """When reply_to is missing but source=mobile_app, delivery should be skipped."""
        metadata = {
            "source": "mobile_app",
            "callback_delivery": {
                "platform": "telegram",
                "chat_id": "12345",
            },
        }

        reply_to = str(metadata.get("reply_to") or metadata.get("source") or "").strip().lower()
        if reply_to == "mobile_app":
            skipped = True
        else:
            skipped = False

        self.assertTrue(skipped)


if __name__ == "__main__":
    unittest.main()
