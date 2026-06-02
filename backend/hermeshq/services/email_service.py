"""Email service using Resend API (https://resend.com)."""

import logging
from typing import Any

import httpx

from hermeshq.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared HTTP client (lazily initialized, reused across calls)
# ---------------------------------------------------------------------------

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """Return a shared httpx.AsyncClient, creating one if needed."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30)
    return _http_client


class EmailServiceError(RuntimeError):
    """Raised when the email service fails to send."""


class EmailService:
    """Sends transactional emails via the Resend API."""

    def __init__(self) -> None:
        self._load_config()

    def _load_config(self) -> None:
        settings = get_settings()
        self._api_key: str = settings.resend_api_key or ""
        self._from_email: str = settings.from_email or "HermesHQ <noreply@resend.dev>"
        self._from_name: str = settings.from_name or settings.app_name
        self._public_base_url: str = settings.public_base_url or "http://localhost:3420"
        self._app_name: str = settings.app_name

    @property
    def is_configured(self) -> bool:
        """Check if the service has the minimum config to send emails."""
        return bool(self._api_key)

    def reload_config(self) -> None:
        """Reload config from env vars only. For async DB reload use areload_config."""
        self._load_config()

    async def areload_config(self) -> None:
        """Reload config from settings (env vars) + database (AppSettings)."""
        self._load_config()
        from hermeshq.models.app_settings import AppSettings
        from hermeshq.database import AsyncSessionLocal
        from sqlalchemy import select

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(AppSettings).where(AppSettings.id == "default"))
                db_settings = result.scalar_one_or_none()
            if db_settings:
                if db_settings.resend_api_key:
                    self._api_key = db_settings.resend_api_key
                if db_settings.from_email:
                    self._from_email = db_settings.from_email
                if db_settings.from_name:
                    self._from_name = db_settings.from_name
                if db_settings.public_base_url:
                    self._public_base_url = db_settings.public_base_url
                if db_settings.app_name:
                    self._app_name = db_settings.app_name
        except Exception:
            logger.debug("Failed to load email settings from DB; using env vars", exc_info=True)

    async def send_password_reset(
        self,
        to_email: str,
        token: str,
        display_name: str,
    ) -> None:
        """Send a password reset email with a one-time link."""
        if not self.is_configured:
            raise EmailServiceError(
                "Resend API key is not configured. "
                "Set RESEND_API_KEY in Settings → Email or via RESEND_API_KEY env var."
            )

        reset_url = f"{self._public_base_url}/reset-password?token={token}"
        subject = f"Password Reset — {self._app_name}"
        html = self._build_reset_email_html(reset_url, display_name)

        await self._send(to_email, subject, html)

    async def _send(self, to: str, subject: str, html: str) -> dict[str, Any]:
        """Low-level send via Resend REST API."""
        payload = {
            "from": self._from_email,
            "to": [to],
            "subject": subject,
            "html": html,
        }
        try:
            client = _get_http_client()
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=15,
            )
            if resp.status_code >= 400:
                body = resp.text[:500]
                logger.error("Resend API error %d: %s", resp.status_code, body)
                raise EmailServiceError(f"Resend API returned {resp.status_code}: {body}")
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("Resend HTTP error: %s", exc)
            raise EmailServiceError(f"Failed to contact Resend: {exc}") from exc

    def _build_reset_email_html(self, reset_url: str, display_name: str) -> str:
        app = self._app_name
        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
             background-color: #0a0a0a; color: #ededed; margin: 0; padding: 32px;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td align="center">
        <table width="480" cellpadding="0" cellspacing="0"
               style="background-color: #141414; border: 1px solid #262626;
                      border-radius: 16px; padding: 40px;">
          <tr>
            <td style="padding-bottom: 24px;">
              <h2 style="margin: 0; color: #ededed; font-size: 22px;">
                Password Reset Request
              </h2>
            </td>
          </tr>
          <tr>
            <td style="padding-bottom: 20px; color: #a0a0a0; font-size: 15px; line-height: 1.6;">
              Hello {display_name},<br><br>
              We received a request to reset your password for your
              <strong style="color: #ededed;">{app}</strong> account.
            </td>
          </tr>
          <tr>
            <td align="center" style="padding-bottom: 24px;">
              <a href="{reset_url}"
                 style="display: inline-block; background-color: #2563eb; color: #ffffff;
                        text-decoration: none; padding: 14px 32px; border-radius: 10px;
                        font-size: 15px; font-weight: 600;">
                Reset Password
              </a>
            </td>
          </tr>
          <tr>
            <td style="color: #a0a0a0; font-size: 13px; line-height: 1.6;">
              This link expires in <strong style="color: #ededed;">15 minutes</strong>.
              If you did not request a password reset, you can safely ignore this email.<br><br>
              Alternatively, copy and paste this URL into your browser:<br>
              <span style="color: #60a5fa; word-break: break-all;">{reset_url}</span>
            </td>
          </tr>
          <tr>
            <td style="padding-top: 24px; border-top: 1px solid #262626;
                        color: #555; font-size: 12px; text-align: center;">
              {app} — Secure Operations Platform
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# Singleton
_email_service: EmailService | None = None


def get_email_service() -> EmailService:
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
