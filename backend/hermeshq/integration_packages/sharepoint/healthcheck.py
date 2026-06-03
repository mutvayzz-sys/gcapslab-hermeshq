async def test_connection(config: dict, resolve_secret):
    """Delegated integration - connection is valid if the integration is enabled.
    Actual user token validation happens at runtime via the M365 OAuth flow."""
    site_url = str(config.get("site_url") or "").strip()
    if site_url:
        return True, f"SharePoint ready (delegated auth — site: {site_url}).", None
    return True, "SharePoint ready (delegated auth — all accessible sites).", None
