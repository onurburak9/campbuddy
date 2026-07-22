# Schema Changes (Alembic)

Every change to `db/models.py` must be accompanied by a migration file in the same commit/PR. The CI `migrations` workflow enforces this by running `alembic check`, which fails if the models have drifted from the applied migrations.

## Adding a column or table

```bash
# 1. Edit db/models.py
# 2. Generate the migration
alembic revision --autogenerate -m "add <description>"
# 3. Review the generated file in migrations/versions/
# 4. Commit both files together
```

## Verifying locally

```bash
# Apply all migrations to a blank database
mkdir -p data
DATABASE_URL="sqlite:///./data/campbuddy.db" alembic upgrade head

# Confirm no drift between models and migrations
DATABASE_URL="sqlite:///./data/campbuddy.db" alembic check
```

## What CI checks

- `alembic upgrade head` — migrations apply cleanly to a blank database
- `alembic check` — no schema drift (catches `db/models.py` changes without a matching migration)

A PR that modifies `db/models.py` without a new migration file will fail the `alembic check` step.

## How migrations run in production (docker compose)

`entrypoint.sh` runs `alembic upgrade head` automatically before starting the scheduler:

```sh
#!/bin/sh
set -e
alembic upgrade head
exec python main.py
```

This only fires for the **`app`** service in `docker-compose.yml`, which uses the
Dockerfile's default `CMD`. The **`api`** service overrides `command: uvicorn
api.main:app ...`, which replaces the entrypoint entirely — `api` never runs
migrations itself, it just reads/writes against whatever schema is already there.

`api`'s `depends_on: app` only waits for the `app` container to *start*, not for
its migration step to *finish* — there's a small window where `api` could begin
serving requests before `app`'s `alembic upgrade head` completes.

For an additive, nullable-column migration (no backfill, no rewrite, no index
rebuild) this window is harmless: worst case `api` is briefly a few hundred
milliseconds ahead of the schema, and nothing queries the new column until well
after the migration is done. For a riskier migration — a `NOT NULL` backfill, an
index rebuild on a large table, anything with real lock duration — don't rely on
this ordering. Instead:

- Run the migration explicitly before bringing the stack up: `docker compose run
  --rm app alembic upgrade head`, then `docker compose up -d`
- Or gate `api`'s `depends_on` on a healthcheck that only passes after `app` has
  finished migrating

Routine deploy for a schema change that follows the "Adding a column or table"
pattern above (nullable, no backfill) is just:

```bash
git pull origin main
docker compose build
docker compose up -d
```
