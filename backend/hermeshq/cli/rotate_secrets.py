#!/usr/bin/env python3
"""Rotate encrypted secrets when JWT_SECRET or FERNET_KEY changes.

Usage:
    # Dry-run (shows what would change, no writes):
    python -m hermeshq.cli.rotate_secrets --dry-run

    # Perform rotation:
    python -m hermeshq.cli.rotate_secrets

This script:
1. Reads the current secrets from the database.
2. Decrypts them using the OLD seed (old JWT_SECRET or FERNET_KEY).
3. Re-encrypts them using the NEW seed.
4. Updates the database rows in a single transaction.

Set environment variables before running:
    DATABASE_URL   — Postgres connection string
    OLD_JWT_SECRET — The JWT_SECRET that was used to encrypt existing secrets
    JWT_SECRET     — The new JWT_SECRET (or keep old if only changing FERNET_KEY)
    FERNET_KEY     — (optional) dedicated Fernet key for SecretVault
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from hermeshq.models.secret import Secret
from hermeshq.services.secret_vault import SecretVault


async def rotate(dry_run: bool = False) -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL environment variable is required.")
        sys.exit(1)

    old_seed = os.environ.get("OLD_JWT_SECRET", "")
    if not old_seed:
        print("❌ OLD_JWT_SECRET environment variable is required (the value used to encrypt existing secrets).")
        sys.exit(1)

    new_fernet = os.environ.get("FERNET_KEY", "")
    new_jwt = os.environ.get("JWT_SECRET", "")
    new_seed = new_fernet or new_jwt
    if not new_seed:
        print("❌ Either FERNET_KEY or JWT_SECRET must be set for the new encryption seed.")
        sys.exit(1)

    if old_seed == new_seed and not dry_run:
        print("⚠️  OLD_JWT_SECRET and new seed are the same — nothing to rotate.")
        print("   Set a new JWT_SECRET or FERNET_KEY before running this script.")
        sys.exit(0)

    old_vault = SecretVault(old_seed)
    new_vault = SecretVault(new_seed)

    engine = create_async_engine(db_url)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        result = await session.execute(select(Secret).order_by(Secret.name))
        secrets = result.scalars().all()

        if not secrets:
            print("No secrets found in database. Nothing to rotate.")
            return

        print(f"Found {len(secrets)} secret(s):")
        rotated = 0
        failed = 0
        for secret in secrets:
            try:
                plaintext = old_vault.decrypt(secret.value_enc)
                if dry_run:
                    print(f"  ✅ {secret.name}: would re-encrypt ({len(plaintext)} chars)")
                else:
                    secret.value_enc = new_vault.encrypt(plaintext)
                    print(f"  ✅ {secret.name}: re-encrypted")
                rotated += 1
            except Exception as exc:  # noqa: BLE001  # decrypt can fail in many ways
                print(f"  ❌ {secret.name}: FAILED to decrypt — {exc}")
                failed += 1

        if not dry_run and rotated > 0:
            await session.commit()
            print(f"\n✅ Committed {rotated} re-encrypted secret(s).")
        elif dry_run:
            print(f"\n📋 Dry run: {rotated} would succeed, {failed} would fail.")

        if failed > 0:
            print(f"\n⚠️  {failed} secret(s) could not be decrypted with OLD_JWT_SECRET.")
            print("   These secrets may need to be re-created manually.")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Rotate HermesHQ encrypted secrets")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    args = parser.parse_args()
    asyncio.run(rotate(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
