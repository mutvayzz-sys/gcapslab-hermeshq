---
name: alembic-migration
description: Generate, review, and apply an Alembic database migration. Use when models have changed and a new migration is needed. Accepts an optional description argument.
disable-model-invocation: true
---

Generate, review, and apply an Alembic migration for HermesHQ.

Steps:

1. If `$ARGUMENTS` is provided, use it as the migration message. Otherwise ask: "Brief migration description?" (used as the `-m` flag value).

2. Tell the user to run on the Mac Mini host:
   ```bash
   alembic -c backend/alembic.ini revision --autogenerate -m "<message>"
   ```

3. After the file is generated (in `backend/hermeshq/alembic/versions/`), ask the user to open and review it. Remind them:
   - Autogenerate misses some cases: complex constraints, partial indexes, column reordering, server defaults
   - Check that the `upgrade()` and `downgrade()` functions are both correct
   - If the migration drops or alters a column, confirm it's intentional

4. Once the user confirms the migration looks correct, tell them to apply it:
   ```bash
   alembic -c backend/alembic.ini upgrade head
   ```

5. Confirm success by asking the user to check the alembic_version table or run the app and verify the schema.
