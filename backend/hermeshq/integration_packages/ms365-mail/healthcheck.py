async def test_connection(config: dict, resolve_secret):
    """Delegated integration - connection is valid if the integration is enabled.
    Actual user token validation happens at runtime via the M365 OAuth flow."""
    return True, "Microsoft 365 Mail ready (delegated auth — user connects their own account).", None
