# Availability Lifecycle Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve `scan_results` from notification-shaped to availability-shaped by adding `last_seen_at` and `is_available`, so the web UI can show whether a site is still available and when it was last seen (ADR 007, Option A — GitHub issue #18).

**Architecture:** Add two columns to `ScanResult`. After each successful run, the runner performs one key-based pass over that scan's result rows: rows whose `(campsite_id, booking_date)` is in the current run's matching set get `last_seen_at` bumped and `is_available=True`; previously-available rows whose key is absent get `is_available=False`. This is purely additive — it does not change the existing dedup key (`ix_scan_results_dedup`), the insert path, or notification behaviour. The API exposes both new fields.

**Tech Stack:** Python 3.11, SQLAlchemy 2 (mapped columns), Alembic, SQLite, pydantic v1, FastAPI, pytest + pytest-mock.

## Global Constraints

- **Virtualenv:** all commands run inside `.venv` (camply pins pydantic v1). Prefix with `.venv/bin/` or activate first. Copied from `CLAUDE.md`.
- **Tests:** mock all external I/O (camply/`check_availability`, Playwright/`attempt_cart_add`, `notify`/`notify_digest`, `decrypt_password`); use in-memory SQLite. Copied from `CLAUDE.md` agent rules / `docs/agents/testing.md`.
- **Datetimes:** always timezone-aware UTC via the module `_now()`/`_utcnow()` helpers; columns are `DateTime(timezone=True)`. Copied from `docs/agents/code-conventions.md`.
- **Schema changes:** any change to `db/models.py` ships with an Alembic migration in the **same commit** — CI runs `alembic upgrade head` then `alembic check` and fails on drift. Copied from `docs/agents/schema-changes.md`.
- **Scope:** data layer only (model + migration + runner + API + tests). Frontend badges are a separate follow-up PR and are intentionally **not** in this plan.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `db/models.py` | ORM schema | Add `last_seen_at`, `is_available` to `ScanResult` (Task 1) |
| `migrations/versions/<rev>_add_availability_lifecycle_to_scan_results.py` | DB migration | Add columns + backfill (Task 1) |
| `tests/test_models.py` | Model tests | Add `last_seen_at` to 4 constructors; assert defaults (Task 1) |
| `tests/services/test_history.py` | Service test helper | Add `last_seen_at` to `_make_result` (Task 1) |
| `tests/api/conftest.py` | API test fixture | Add `last_seen_at` to seeded `ScanResult` (Task 1) |
| `core/runner.py` | Availability lifecycle logic | New key-based pass; stamp new rows (Task 2) |
| `tests/test_runner.py` | Runner tests | Re-find / drop-out / reappearance / new-row tests (Task 2) |
| `api/schemas.py` | API response schema | Add 2 fields to `ScanResultResponse` (Task 3) |
| `tests/api/test_schemas.py` | Schema test | Assert new fields serialize (Task 3) |

---

## Task 1: Add columns + migration + fix all constructors

Model change and migration ship together so every commit stays CI-green (`alembic check` would fail on a model-only commit). All existing `ScanResult(...)` constructors must gain `last_seen_at` because the column is `NOT NULL`.

**Files:**
- Modify: `db/models.py` (`ScanResult`, after `first_seen_at` at `db/models.py:143`)
- Create: `migrations/versions/<generated-rev>_add_availability_lifecycle_to_scan_results.py`
- Modify: `tests/test_models.py:104,135,180,222` (four `ScanResult(...)` constructors)
- Modify: `tests/services/test_history.py:26` (`_make_result`)
- Modify: `tests/api/conftest.py:123` (seeded `ScanResult`)

**Interfaces:**
- Produces: `ScanResult.last_seen_at: datetime` (tz-aware, NOT NULL), `ScanResult.is_available: bool` (NOT NULL, default `True`). Later tasks (runner, API) rely on exactly these names/types.

- [ ] **Step 1: Write the failing model test**

In `tests/test_models.py`, replace the body of `test_scan_result_defaults` (starts at `tests/test_models.py:90`) so it sets and asserts the new fields:

```python
def test_scan_result_defaults(db):
    user = User(email="test@example.com")
    db.add(user)
    db.flush()
    scan = _make_scan(db, user)
    run = ScanRun(
        scan_id=scan.id,
        started_at=_now(),
        finished_at=_now(),
        outcome=ScanOutcome.success,
        sites_found=1,
    )
    db.add(run)
    db.flush()
    now = _now()
    result = ScanResult(
        scan_run_id=run.id,
        scan_id=scan.id,
        campsite_id="10357088",
        facility_name="Union West",
        site_name="1",
        campsite_type="STANDARD NONELECTRIC",
        booking_date=date(2026, 7, 3),
        booking_end_date=date(2026, 7, 6),
        booking_url="https://www.recreation.gov/camping/campsites/10357088",
        first_seen_at=now,
        last_seen_at=now,
    )
    db.add(result)
    db.commit()
    assert result.id is not None
    assert result.cart_added is False
    assert result.notified is False
    assert result.cart_added_at is None
    assert result.last_seen_at == now
    assert result.is_available is True  # column default applied on insert
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_models.py::test_scan_result_defaults -v`
Expected: FAIL — `TypeError: 'last_seen_at' is an invalid keyword argument` (or an integrity/attribute error on `is_available`).

- [ ] **Step 3: Add the columns to the model**

In `db/models.py`, in class `ScanResult`, immediately after the `first_seen_at` line (`db/models.py:143`) add:

```python
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

- [ ] **Step 4: Add `last_seen_at` to the other test constructors**

These constructors currently omit `last_seen_at` and will now fail with `IntegrityError` (NOT NULL). In `tests/test_models.py`, in each of the three remaining `ScanResult(...)` constructors (at `:135`, `:180`, `:222`), add `last_seen_at=_now(),` on the line directly after `first_seen_at=_now(),`.

In `tests/services/test_history.py`, update `_make_result` (`:26`) so the constructor includes it — change:

```python
        first_seen_at=datetime.now(timezone.utc),
    )
```
to:
```python
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
```

In `tests/api/conftest.py`, in the `ScanResult(...)` constructor (`:123`), add `last_seen_at=...` matching the same value expression already used for `first_seen_at` on the adjacent line (use the identical right-hand side, e.g. `last_seen_at=now,` or `last_seen_at=datetime.now(timezone.utc),` — match whatever `first_seen_at` uses there).

- [ ] **Step 5: Generate the migration scaffold**

Create a fresh blank DB at the current head, then autogenerate:

```bash
rm -f data/campbuddy.db && mkdir -p data
DATABASE_URL="sqlite:///./data/campbuddy.db" .venv/bin/alembic upgrade head
DATABASE_URL="sqlite:///./data/campbuddy.db" .venv/bin/alembic revision --autogenerate -m "add availability lifecycle to scan_results"
```

This writes a new file under `migrations/versions/`. Note its generated `revision` id; keep the generated `revision`/`down_revision` lines (`down_revision` will be `'e48548624895'`).

- [ ] **Step 6: Replace the migration body**

The autogenerated `upgrade()` will try to add both columns `NOT NULL` with no backfill, which fails on any table with existing rows. Replace the `upgrade()` and `downgrade()` bodies (keep the generated header/revision lines and imports) with:

```python
def upgrade() -> None:
    # Add is_available NOT NULL with a server-side default so existing rows get True.
    # Add last_seen_at nullable first; backfill from first_seen_at; then enforce NOT NULL.
    with op.batch_alter_table("scan_results") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_available",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.add_column(
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True)
        )

    op.execute("UPDATE scan_results SET last_seen_at = first_seen_at WHERE last_seen_at IS NULL")

    with op.batch_alter_table("scan_results") as batch_op:
        batch_op.alter_column(
            "last_seen_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("scan_results") as batch_op:
        batch_op.drop_column("last_seen_at")
        batch_op.drop_column("is_available")
```

Ensure `import sqlalchemy as sa` and `from alembic import op` are present (autogenerate adds them).

- [ ] **Step 7: Verify migration applies cleanly and matches the model**

```bash
rm -f data/campbuddy.db
DATABASE_URL="sqlite:///./data/campbuddy.db" .venv/bin/alembic upgrade head
DATABASE_URL="sqlite:///./data/campbuddy.db" .venv/bin/alembic check
```
Expected: `upgrade` runs without error; `alembic check` prints `No new upgrade operations detected.` (no drift between `db/models.py` and the migrations).

- [ ] **Step 8: Verify the backfill against a pre-existing row**

Confirm existing rows get sensible values (last_seen := first_seen, is_available := true):

```bash
rm -f data/campbuddy.db
# Stamp DB at the PREVIOUS head, insert a legacy row, then upgrade and inspect.
DATABASE_URL="sqlite:///./data/campbuddy.db" .venv/bin/alembic upgrade e48548624895
.venv/bin/python - <<'PY'
import sqlite3
c = sqlite3.connect("data/campbuddy.db")
c.execute("INSERT INTO users (email, created_at, scan_limit) VALUES ('a@b.c', '2026-01-01', 5)")
c.execute("INSERT INTO scans (user_id, provider, status, polling_interval, search_windows, nights, weekends_only, notify_via_email, notify_via_telegram, notify_on_new_only, created_at) VALUES (1,'RecreationDotGov','active',300,'[]',1,0,1,0,1,'2026-01-01')")
c.execute("INSERT INTO scan_runs (scan_id, started_at, sites_found) VALUES (1,'2026-01-01',1)")
c.execute("INSERT INTO scan_results (scan_run_id, scan_id, campsite_id, facility_name, site_name, campsite_type, booking_date, booking_end_date, booking_url, first_seen_at, cart_added, notified) VALUES (1,1,'x','F','S','T','2026-07-03','2026-07-06','http://x','2026-06-01T00:00:00+00:00',0,0)")
c.commit(); c.close()
PY
DATABASE_URL="sqlite:///./data/campbuddy.db" .venv/bin/alembic upgrade head
.venv/bin/python - <<'PY'
import sqlite3
c = sqlite3.connect("data/campbuddy.db")
row = c.execute("SELECT first_seen_at, last_seen_at, is_available FROM scan_results").fetchone()
print(row)
assert row[1] == row[0], f"last_seen_at should backfill from first_seen_at, got {row}"
assert row[2] == 1, f"is_available should default to 1/true, got {row}"
print("backfill OK")
PY
rm -f data/campbuddy.db
```
Expected: prints `backfill OK`.

- [ ] **Step 9: Run the affected test suites**

Run: `.venv/bin/pytest tests/test_models.py tests/services/test_history.py tests/api -v`
Expected: all PASS (all constructor call sites now supply `last_seen_at`).

- [ ] **Step 10: Commit**

```bash
git add db/models.py migrations/versions/ tests/test_models.py tests/services/test_history.py tests/api/conftest.py
git commit -m "feat(db): add last_seen_at and is_available to scan_results

ADR 007 Option A (#18). Additive columns + backfill migration
(last_seen_at := first_seen_at, is_available := true)."
```

---

## Task 2: Runner availability lifecycle pass

Teach the runner to keep the new columns accurate. New rows are stamped `last_seen_at = first_seen_at`, `is_available = True`. After the site loop (and even on a no-results run), one pass over the scan's rows bumps `last_seen_at`/re-flags present keys and flips absent keys to `is_available = False`. Insert, dedup, cart, and notification behaviour are unchanged.

**Files:**
- Modify: `core/runner.py` (add `_as_date` helper; set fields on insert at `core/runner.py:82-92`; add availability pass before the finalize transaction at `core/runner.py:150`)
- Modify: `tests/test_runner.py` (add four tests)

**Interfaces:**
- Consumes: `ScanResult.last_seen_at`, `ScanResult.is_available` (from Task 1).
- Uses existing `_now()` (`core/runner.py:16`) and the `sites` list from `check_availability` (each item exposes `.campsite_id`, `.booking_date`).

- [ ] **Step 1: Write the failing runner tests**

Append to `tests/test_runner.py` (helpers `make_site`, fixtures `factory`, `scan_id`, `settings` already exist):

```python
def test_re_find_updates_last_seen_at(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mocker.patch("core.runner.notify_digest")
    run_scan(scan_id, factory, settings)
    with factory() as db:
        first = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).one()
        first_seen = first.first_seen_at
        seen_after_run1 = first.last_seen_at
    run_scan(scan_id, factory, settings)
    with factory() as db:
        rows = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).all()
        assert len(rows) == 1  # dedup: still one row
        r = rows[0]
        assert r.first_seen_at == first_seen  # unchanged
        assert r.last_seen_at > seen_after_run1  # bumped on re-find
        assert r.is_available is True


def test_dropout_flips_is_available_false(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", side_effect=[[make_site()], []])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mocker.patch("core.runner.notify_digest")
    run_scan(scan_id, factory, settings)  # site present
    run_scan(scan_id, factory, settings)  # site gone (empty results)
    with factory() as db:
        r = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).one()
        assert r.is_available is False


def test_reappearance_flips_is_available_true(factory, scan_id, settings, mocker):
    mocker.patch(
        "core.runner.check_availability",
        side_effect=[[make_site()], [], [make_site()]],
    )
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mocker.patch("core.runner.notify_digest")
    run_scan(scan_id, factory, settings)  # present
    run_scan(scan_id, factory, settings)  # gone
    with factory() as db:
        assert db.query(ScanResult).filter(ScanResult.scan_id == scan_id).one().is_available is False
    run_scan(scan_id, factory, settings)  # back
    with factory() as db:
        r = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).one()
        assert r.is_available is True


def test_new_row_stamps_last_seen_and_available(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mocker.patch("core.runner.notify_digest")
    run_scan(scan_id, factory, settings)
    with factory() as db:
        r = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).one()
        assert r.last_seen_at is not None
        assert r.last_seen_at >= r.first_seen_at
        assert r.is_available is True
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `.venv/bin/pytest tests/test_runner.py -k "last_seen or is_available or reappearance or new_row" -v`
Expected: FAIL — `test_re_find_updates_last_seen_at` fails on `last_seen_at > seen_after_run1` (runner does not bump), `test_dropout...` fails on `is_available is False` (runner never flips). New-row test may error if the runner still inserts without `last_seen_at` (NOT NULL) — that is also a valid fail.

- [ ] **Step 3: Add the `_as_date` helper**

In `core/runner.py`, directly after the `_now()` function (`core/runner.py:16-17`) add:

```python
def _as_date(value):
    return value.date() if hasattr(value, "date") else value
```

- [ ] **Step 4: Stamp new rows and build the current key set**

In `core/runner.py`, after the `check_availability` try/except block (right before `try:` at `core/runner.py:52`... i.e. as the first statement inside the main `try:` at `core/runner.py:52`), add:

```python
        current_keys = {
            (str(s.campsite_id), _as_date(s.booking_date)) for s in sites
        }
```

Then update the per-site normalisation and the insert. Replace the two inline `booking_date` / `booking_end_date` blocks (`core/runner.py:54-64`) with:

```python
            booking_date = _as_date(site.booking_date)
            booking_end_date = _as_date(site.booking_end_date)
```

And in the `ScanResult(...)` insert (`core/runner.py:82-92`), change the trailing `first_seen_at=_now(),` so both timestamps and availability are set:

```python
                seen = _now()
                result = ScanResult(
                    scan_run_id=run_id,
                    scan_id=scan_id,
                    campsite_id=str(site.campsite_id),
                    facility_name=site.facility_name,
                    site_name=site.campsite_site_name,
                    campsite_type=site.campsite_type,
                    booking_date=booking_date,
                    booking_end_date=booking_end_date,
                    booking_url=site.booking_url,
                    first_seen_at=seen,
                    last_seen_at=seen,
                    is_available=True,
                )
```

- [ ] **Step 5: Add the availability pass before finalize**

In `core/runner.py`, immediately before the `# Transaction 4 (fast): finalize run` block (`core/runner.py:150`), add:

```python
        # Availability lifecycle: bump last_seen for keys present this run,
        # flip previously-available keys that dropped out to unavailable.
        # Runs even when `sites` is empty (everything then goes unavailable).
        now = _now()
        with get_db(session_factory) as db:
            rows = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).all()
            for r in rows:
                if (r.campsite_id, r.booking_date) in current_keys:
                    r.last_seen_at = now
                    r.is_available = True
                elif r.is_available:
                    r.is_available = False
```

- [ ] **Step 6: Run the new runner tests**

Run: `.venv/bin/pytest tests/test_runner.py -k "last_seen or is_available or reappearance or new_row" -v`
Expected: all PASS.

- [ ] **Step 7: Run the full runner suite for regressions**

Run: `.venv/bin/pytest tests/test_runner.py -v`
Expected: all PASS — existing dedup/notification/digest tests are unaffected (insert and notify paths unchanged).

- [ ] **Step 8: Commit**

```bash
git add core/runner.py tests/test_runner.py
git commit -m "feat(runner): track availability lifecycle on scan_results

Stamp last_seen_at/is_available on insert; after each run bump
present keys and flip dropped-out keys to unavailable (ADR 007, #18)."
```

---

## Task 3: Expose the fields in the API

Add the two fields to the results response schema so the UI (future PR) can read them. `ScanResultResponse` uses `orm_mode`, and the routes return ORM objects directly, so no route changes are needed.

**Files:**
- Modify: `api/schemas.py` (`ScanResultResponse`, after `first_seen_at` at `api/schemas.py:158`)
- Create: `tests/api/test_schemas.py`

**Interfaces:**
- Consumes: `ScanResult.first_seen_at`, `ScanResult.last_seen_at`, `ScanResult.is_available` (Task 1).
- Produces: `ScanResultResponse` now carries `last_seen_at: datetime` and `is_available: bool`.

- [ ] **Step 1: Write the failing schema test**

Create `tests/api/test_schemas.py`:

```python
from datetime import datetime, date, timezone

from api.schemas import ScanResultResponse
from db.models import ScanResult


def test_scan_result_response_includes_availability_fields():
    now = datetime.now(timezone.utc)
    result = ScanResult(
        id=1,
        scan_run_id=1,
        scan_id=1,
        campsite_id="1",
        facility_name="F",
        site_name="S",
        campsite_type="T",
        booking_date=date(2026, 7, 3),
        booking_end_date=date(2026, 7, 6),
        booking_url="https://example.com",
        first_seen_at=now,
        last_seen_at=now,
        is_available=True,
        cart_added=False,
        notified=False,
    )
    resp = ScanResultResponse.from_orm(result)
    assert resp.first_seen_at == now
    assert resp.last_seen_at == now
    assert resp.is_available is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/api/test_schemas.py -v`
Expected: FAIL — `AttributeError: 'ScanResultResponse' object has no attribute 'last_seen_at'`.

- [ ] **Step 3: Add the fields to the schema**

In `api/schemas.py`, in `ScanResultResponse`, after `first_seen_at: datetime` (`api/schemas.py:158`) add:

```python
    last_seen_at: datetime
    is_available: bool
```

- [ ] **Step 4: Run the schema test**

Run: `.venv/bin/pytest tests/api/test_schemas.py -v`
Expected: PASS.

- [ ] **Step 5: Run the API suite for regressions**

Run: `.venv/bin/pytest tests/api -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add api/schemas.py tests/api/test_schemas.py
git commit -m "feat(api): expose last_seen_at and is_available on ScanResultResponse (#18)"
```

---

## Final verification

- [ ] **Full suite:** `.venv/bin/pytest tests/ -v` — all PASS.
- [ ] **Migration integrity:** `rm -f data/campbuddy.db && DATABASE_URL="sqlite:///./data/campbuddy.db" .venv/bin/alembic upgrade head && DATABASE_URL="sqlite:///./data/campbuddy.db" .venv/bin/alembic check` — clean upgrade, `No new upgrade operations detected.`

---

## Self-Review

**Spec coverage (ADR 007 / issue #18):**
- `last_seen_at` column + updated on re-observation — Task 1 (column), Task 2 (bump pass). ✓
- `is_available` column + flipped false on drop-out — Task 1 (column), Task 2 (flip pass). ✓
- Runner change localized to persistence, dedup key unchanged — Task 2 leaves insert/dedup/notify paths intact; adds a separate pass. ✓
- Migration adds columns; `is_available` default true; `last_seen_at` backfilled from `first_seen_at` — Task 1, Steps 6–8. ✓
- API: add `last_seen_at` and `is_available` to `ScanResultResponse` — Task 3. ✓
- Reappearance (site returns) handled — Task 2 sets `is_available=True` for present keys (test in Task 2). Additive, not explicitly required by ADR but consistent with it.

**Deferred (out of scope, intentionally):** UI badges (`Available / Gone · last seen Xh ago`) — follow-up PR per the Scope constraint. Option B (`scan_observations` table) — rejected by ADR.

**Placeholder scan:** No TBD/TODO; every code and command step contains concrete content. ✓

**Type consistency:** `last_seen_at: datetime` (tz-aware) and `is_available: bool` used identically across model (Task 1), runner (Task 2), and schema (Task 3); key tuple `(str(campsite_id), date)` built the same way for `current_keys` and compared against `r.campsite_id`/`r.booking_date` (both stored as `str`/`date`). ✓
