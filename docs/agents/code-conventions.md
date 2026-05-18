# Code Conventions

## General

- No comments unless the WHY is non-obvious (a constraint, a workaround, a surprising invariant)
- No docstrings on obvious functions
- Each file has one responsibility — if it grows past ~150 lines, consider splitting

## Database

- DB session always via `get_db()` context manager — never share a Session across threads
- Timezone-aware datetimes everywhere: `datetime.now(timezone.utc)`, never `datetime.utcnow()`
- Every `db/models.py` change must include a migration — see [schema-changes.md](schema-changes.md)
