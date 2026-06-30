#!/usr/bin/env python
"""
Mint a long-lived admin JWT for service-to-service auth (e.g. gcap-console).

Usage:
    python scripts/mint_admin_token.py

Reads JWT_SECRET from the HermesHQ backend .env (or environment).
Outputs a token valid for 1 year.
"""
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


def load_secret_from_env_file(env_path: Path) -> str:
    """Read JWT_SECRET from a .env file without python-dotenv."""
    if not env_path.exists():
        return ""
    for line in env_path.read_text().splitlines():
        if line.strip().startswith("JWT_SECRET="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def main():
    secret = os.environ.get("JWT_SECRET") or load_secret_from_env_file(
        Path("backend/.env")
    )
    if not secret:
        print("ERROR: JWT_SECRET not set", file=sys.stderr)
        sys.exit(1)

    try:
        from jose import jwt
    except ImportError:
        print("ERROR: python-jose not installed", file=sys.stderr)
        sys.exit(1)

    subject = os.environ.get("ADMIN_USERNAME", "admin")
    expires = datetime.now(UTC) + timedelta(days=365)
    payload = {
        "sub": subject,
        "sub_kind": "username",
        "role": "admin",
        "exp": expires,
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    print(token)
    print(f"# valid until {expires.isoformat()}", file=sys.stderr)


if __name__ == "__main__":
    main()