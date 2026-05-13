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
