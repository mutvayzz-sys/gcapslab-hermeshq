from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.models.user import User

_PLATFORM_COLUMN: dict[str, str] = {
    "telegram": "telegram_id",
    "whatsapp": "whatsapp_user",
    "microsoft_teams": "teams_id",
    "google_chat": "google_chat_email",
    # kapso_whatsapp: match the user's WhatsApp phone number stored in kapso_number.
    # The sender_id from Kapso webhooks may or may not include the '+' prefix, so we
    # try both forms.
    "kapso_whatsapp": "kapso_number",
}


async def resolve_channel_user(db: AsyncSession, platform: str, sender_id: str) -> User | None:
    """Return the HermesHQ User whose channel identifier matches sender_id, or None."""
    column_name = _PLATFORM_COLUMN.get(platform)
    if not column_name or not sender_id:
        return None
    column = getattr(User, column_name)
    result = await db.execute(select(User).where(column == sender_id).limit(1))
    user = result.scalar_one_or_none()
    if user:
        return user

    # For Kapso WhatsApp, the webhook may omit the '+' prefix while the stored
    # kapso_number includes it (or vice-versa).  Try the alternate form.
    if platform == "kapso_whatsapp":
        if sender_id.startswith("+"):
            alt_id = sender_id[1:]
        else:
            alt_id = "+" + sender_id
        result2 = await db.execute(select(User).where(column == alt_id).limit(1))
        return result2.scalar_one_or_none()

    return None
