from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from hermeshq.models.app_settings import AppSettings
from hermeshq.models.user_m365_token import UserM365Token
from hermeshq.services.secret_vault import SecretVault

if TYPE_CHECKING:
    pass

# Scopes disponibles que el admin puede habilitar, mapeados a nombre legible
# Deben coincidir exactamente con los permisos concedidos en el registro de Azure AD
AVAILABLE_SCOPES: dict[str, str] = {
    "User.Read": "Perfil del usuario",
    # Mail
    "Mail.Read": "Leer correos",
    "Mail.Send": "Enviar correos",
    # Calendar
    "Calendars.Read": "Leer calendario",
    "Calendars.ReadWrite": "Leer y escribir calendario",
    # Files / SharePoint / OneDrive (delegated)
    "Files.Read.All": "Leer archivos SharePoint y OneDrive",
    # Teams / Chat
    "Chat.Read": "Leer chats de Teams",
    "Chat.ReadWrite": "Leer y escribir chats de Teams",
    "Team.ReadBasic.All": "Leer equipos de Teams",
}

# User.Read siempre requerido para identificar al usuario
REQUIRED_SCOPES = ["User.Read"]


class M365ConfigError(RuntimeError):
    pass


class M365TokenError(RuntimeError):
    pass


def _get_msal():
    try:
        import msal
        return msal
    except ImportError as exc:
        raise M365ConfigError("msal no está instalado. Ejecuta: pip install msal") from exc


async def get_instance_m365_config(db: AsyncSession) -> dict | None:
    settings = await db.get(AppSettings, "default")
    if not settings:
        return None
    client_id = (settings.m365_client_id or "").strip()
    tenant_id = (settings.m365_tenant_id or "").strip()
    if not client_id or not tenant_id:
        return None
    enabled_scopes = list(settings.m365_enabled_scopes or [])
    return {
        "client_id": client_id,
        "tenant_id": tenant_id,
        "authority": f"https://login.microsoftonline.com/{tenant_id}",
        "enabled_scopes": enabled_scopes,
    }


def _build_scopes(enabled_scopes: list[str]) -> list[str]:
    scopes = list(REQUIRED_SCOPES)
    for scope in enabled_scopes:
        if scope in AVAILABLE_SCOPES and scope not in scopes:
            scopes.append(scope)
    return scopes


async def initiate_device_flow(db: AsyncSession) -> dict:
    config = await get_instance_m365_config(db)
    if not config:
        raise M365ConfigError("Microsoft 365 no está configurado en esta instancia.")

    msal = _get_msal()
    app = msal.PublicClientApplication(
        config["client_id"],
        authority=config["authority"],
    )
    scopes = _build_scopes(config["enabled_scopes"])
    flow = app.initiate_device_flow(scopes=scopes)
    if "user_code" not in flow:
        raise M365ConfigError(f"Error al iniciar autenticación: {flow.get('error_description', 'unknown')}")

    return {
        "verification_uri": flow["verification_uri"],
        "user_code": flow["user_code"],
        "expires_in": flow.get("expires_in", 900),
        "_flow": flow,
        "_config": config,
    }


async def complete_device_flow(
    flow_state: dict,
    vault: SecretVault,
    db: AsyncSession,
    user_id: str,
) -> UserM365Token:
    msal = _get_msal()
    config = flow_state["_config"]
    flow = flow_state["_flow"]

    cache = msal.SerializableTokenCache()
    app = msal.PublicClientApplication(
        config["client_id"],
        authority=config["authority"],
        token_cache=cache,
    )

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, lambda: app.acquire_token_by_device_flow(flow)
    )

    if "access_token" not in result:
        error = result.get("error_description") or result.get("error") or "Error desconocido"
        raise M365TokenError(f"Autenticación fallida: {error}")

    claims = result.get("id_token_claims") or {}
    account_email = str(claims.get("preferred_username") or "").strip()
    account_name = str(claims.get("name") or "").strip() or None

    granted_scopes = result.get("scope", "").split()
    scopes_str = " ".join(s for s in granted_scopes if s not in ("openid", "profile", "email"))

    expires_at = None
    if result.get("expires_in"):
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(result["expires_in"]))

    cache_json = cache.serialize()
    token_cache_enc = vault.encrypt(cache_json)

    existing = await db.execute(
        select(UserM365Token).where(UserM365Token.user_id == user_id)
    )
    token_record = existing.scalar_one_or_none()

    if token_record:
        token_record.account_email = account_email
        token_record.account_name = account_name
        token_record.token_cache_enc = token_cache_enc
        token_record.scopes = scopes_str
        token_record.expires_at = expires_at
        token_record.revoked_at = None
    else:
        token_record = UserM365Token(
            user_id=user_id,
            account_email=account_email,
            account_name=account_name,
            token_cache_enc=token_cache_enc,
            scopes=scopes_str,
            expires_at=expires_at,
        )
        db.add(token_record)

    await db.commit()
    await db.refresh(token_record)
    return token_record


async def get_valid_token(
    user_id: str,
    vault: SecretVault,
    db: AsyncSession,
) -> tuple[str, str, list[str]] | tuple[None, None, None]:
    result = await db.execute(
        select(UserM365Token).where(
            UserM365Token.user_id == user_id,
            UserM365Token.revoked_at.is_(None),
        )
    )
    token_record = result.scalar_one_or_none()
    if not token_record:
        return None, None, None

    config = await get_instance_m365_config(db)
    if not config:
        return None, None, None

    msal = _get_msal()
    cache = msal.SerializableTokenCache()
    try:
        cache.deserialize(vault.decrypt(token_record.token_cache_enc))
    except Exception:
        return None, None, None

    app = msal.PublicClientApplication(
        config["client_id"],
        authority=config["authority"],
        token_cache=cache,
    )

    accounts = app.get_accounts()
    if not accounts:
        return None, None, None

    scopes = _build_scopes(config["enabled_scopes"])
    result_token = app.acquire_token_silent(scopes, account=accounts[0])

    if not result_token or "access_token" not in result_token:
        return None, None, None

    if cache.has_state_changed:
        token_record.token_cache_enc = vault.encrypt(cache.serialize())
        if result_token.get("expires_in"):
            from datetime import timedelta
            token_record.expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=int(result_token["expires_in"])
            )
        await db.commit()

    granted_scopes = token_record.scopes.split() if token_record.scopes else []
    return result_token["access_token"], token_record.account_email, granted_scopes


async def revoke_user_token(user_id: str, db: AsyncSession) -> bool:
    result = await db.execute(
        select(UserM365Token).where(UserM365Token.user_id == user_id)
    )
    token_record = result.scalar_one_or_none()
    if not token_record:
        return False
    token_record.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    return True
