# last_seen_at Re-notification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When `notify_on_new_only=True`, re-notify users about a campsite that went unavailable and came back, by tracking `last_seen_at` on `ScanResult` and comparing it against the previous completed `ScanRun.started_at`.

**Architecture:** Add a `last_seen_at` column to `ScanResult` that is stamped on every scan where the site appears. In `run_scan`, fetch the previous completed run's `started_at` once in Transaction 1. For each site, upsert the `ScanResult` — updating `last_seen_at` if the row exists, creating it if not. Notify only when the row is new OR when the old `last_seen_at` predates the previous run's start (indicating an availability gap). A lightweight migration handles existing databases by backfilling `last_seen_at = first_seen_at`.

**Tech Stack:** Python 3, SQLAlchemy 2 (mapped columns), SQLite, pytest + pytest-mock

---

## File Map

| File | Change |
|------|--------|
| `db/models.py` | Add `last_seen_at` to `ScanResult` |
| `db/session.py` | Add `migrate_db()` for existing databases |
| `main.py` | Call `migrate_db()` after `create_tables()` |
| `cli.py` | Call `migrate_db()` after `create_tables()` |
| `core/runner.py` | Fetch prev_run in Transaction 1; upsert with absence detection in Transaction 2 |
| `tests/test_models.py` | Add `last_seen_at` to every `ScanResult(...)` constructor; assert new field |
| `tests/test_runner.py` | Update existing dedup tests; add three new re-notification tests |

---

## Task 1: Add `last_seen_at` to `ScanResult` model

**Files:**
- Modify: `db/models.py` (after `first_seen_at` line ~143)
- Modify: `tests/test_models.py` (all `ScanResult(...)` constructors)

- [ ] **Step 1: Write the failing test**

In `tests/test_models.py`, replace the existing `test_scan_result_defaults` function:

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
    assert result.first_seen_at == result.last_seen_at
```

Also add `last_seen_at=_now(),` after `first_seen_at=_now(),` in every other `ScanResult(...)` constructor in `tests/test_models.py` (four locations: lines ~135, ~180, ~222, ~135 in cascade tests).

- [ ] **Step 2: Run test to verify it fails**

```
.venv/bin/pytest tests/test_models.py::test_scan_result_defaults -v
```

Expected: FAIL with `unexpected keyword argument 'last_seen_at'` or integrity error.

- [ ] **Step 3: Add `last_seen_at` to the model**

In `db/models.py`, add after the `first_seen_at` line:

```python
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

- [ ] **Step 4: Run the full model test suite**

```
.venv/bin/pytest tests/test_models.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add db/models.py tests/test_models.py
git commit -m "feat: add last_seen_at column to ScanResult"
```

---

## Task 2: Add `migrate_db()` for existing databases

New installs get `last_seen_at` from `create_all`. Existing SQLite databases need `ALTER TABLE` + backfill.

**Files:**
- Modify: `db/session.py`
- Modify: `main.py`
- Modify: `cli.py`
- Modify: `tests/test_models.py` (add migration tests)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_models.py` (add `from sqlalchemy import text` to imports, and `migrate_db` to the `db.session` import):

```python
from sqlalchemy import text
from db.session import create_tables, get_db, make_engine, make_session_factory, migrate_db


def test_migrate_db_adds_last_seen_at_column():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE scan_results DROP COLUMN last_seen_at"))
        conn.commit()
        cols_before = {row[1] for row in conn.execute(text("PRAGMA table_info(scan_results)"))}
    assert "last_seen_at" not in cols_before

    migrate_db(engine)

    with engine.connect() as conn:
        cols_after = {row[1] for row in conn.execute(text("PRAGMA table_info(scan_results)"))}
    assert "last_seen_at" in cols_after


def test_migrate_db_backfills_last_seen_at_from_first_seen_at():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO users (email, created_at) VALUES ('m@x.com', '2026-01-01T00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO scans (user_id, provider, status, polling_interval, search_windows, "
            "nights, weekends_only, notify_via_email, notify_via_telegram, notify_on_new_only) "
            "VALUES (1, 'RecreationDotGov', 'active', 300, '[]', 1, 0, 1, 0, 1)"
        ))
        conn.execute(text(
            "INSERT INTO scan_runs (scan_id, started_at) VALUES (1, '2026-01-01T00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO scan_results (scan_run_id, scan_id, campsite_id, facility_name, "
            "site_name, campsite_type, booking_date, booking_end_date, booking_url, "
            "first_seen_at, last_seen_at) VALUES "
            "(1, 1, '99', 'F', 'S', 'T', '2026-07-03', '2026-07-04', 'http://x', "
            "'2026-05-01T10:00:00', '2026-05-01T10:00:00')"
        ))
        conn.commit()
        conn.execute(text("ALTER TABLE scan_results DROP COLUMN last_seen_at"))
        conn.commit()

    migrate_db(engine)

    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT first_seen_at, last_seen_at FROM scan_results WHERE campsite_id='99'"
        )).fetchone()
    assert row[1] == row[0]


def test_migrate_db_is_idempotent():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    migrate_db(engine)
    migrate_db(engine)  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv/bin/pytest tests/test_models.py::test_migrate_db_adds_last_seen_at_column tests/test_models.py::test_migrate_db_is_idempotent -v
```

Expected: FAIL with `ImportError: cannot import name 'migrate_db'`.

- [ ] **Step 3: Add `migrate_db()` to `db/session.py`**

Add `from sqlalchemy import text` to the imports in `db/session.py`, then add after `create_tables`:

```python
def migrate_db(engine) -> None:
    with engine.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(scan_results)"))}
        if "last_seen_at" not in cols:
            conn.execute(text("ALTER TABLE scan_results ADD COLUMN last_seen_at DATETIME"))
            conn.execute(text("UPDATE scan_results SET last_seen_at = first_seen_at"))
            conn.commit()
```

- [ ] **Step 4: Wire `migrate_db` into `main.py`**

Update import:

```python
from db.session import make_engine, create_tables, migrate_db, make_session_factory
```

Call it after `create_tables`:

```python
    engine = make_engine(settings.database_url)
    create_tables(engine)
    migrate_db(engine)
    session_factory = make_session_factory(engine)
```

- [ ] **Step 5: Wire `migrate_db` into `cli.py`**

Update the `db.session` import in `cli.py` to include `migrate_db`, then call `migrate_db(engine)` immediately after `create_tables(engine)`.

- [ ] **Step 6: Run migration tests**

```
.venv/bin/pytest tests/test_models.py -v
```

Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add db/session.py main.py cli.py tests/test_models.py
git commit -m "feat: add migrate_db to backfill last_seen_at on existing databases"
```

---

## Task 3: Update runner — prev_run fetch and upsert logic

**Files:**
- Modify: `core/runner.py`
- Modify: `tests/test_runner.py`

Two changes to the runner:
1. **Transaction 1** — fetch the last completed `ScanRun` for this scan (before the current run) and extract its `started_at` as a plain datetime.
2. **Transaction 2** — upsert: update `last_seen_at` if row exists, create if not. When `notify_on_new_only=True` and `old_last_seen >= prev_run_started_at`, the site was continuously available — commit the `last_seen_at` update but skip notification.

- [ ] **Step 1: Write the failing tests**

In `tests/test_runner.py`, remove `test_dedup_skips_same_site_same_date` and `test_dedup_notifies_same_site_different_date` (both superseded). Add:

```python
def test_dedup_skips_continuously_available_site(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mock_notify = mocker.patch("core.runner.notify")
    run_scan(scan_id, factory, settings)
    run_scan(scan_id, factory, settings)
    assert mock_notify.call_count == 1


def test_dedup_renotifies_after_absence(factory, scan_id, settings, mocker):
    # Run 1: site found. Run 2: site absent. Run 3: site found again — should re-notify.
    mocker.patch(
        "core.runner.check_availability",
        side_effect=[[make_site()], [], [make_site()]],
    )
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mock_notify = mocker.patch("core.runner.notify")
    run_scan(scan_id, factory, settings)
    run_scan(scan_id, factory, settings)
    run_scan(scan_id, factory, settings)
    assert mock_notify.call_count == 2


def test_dedup_last_seen_at_updated_when_site_persists(factory, scan_id, settings, mocker):
    mocker.patch("core.runner.check_availability", return_value=[make_site()])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mocker.patch("core.runner.notify")
    run_scan(scan_id, factory, settings)
    with factory() as db:
        first_last_seen = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).first().last_seen_at
    run_scan(scan_id, factory, settings)
    with factory() as db:
        second_last_seen = db.query(ScanResult).filter(ScanResult.scan_id == scan_id).first().last_seen_at
    assert second_last_seen > first_last_seen


def test_dedup_notifies_same_site_different_date(factory, scan_id, settings, mocker):
    site_a = make_site(check_in=date(2026, 7, 3))
    site_b = make_site(check_in=date(2026, 7, 10))
    mocker.patch("core.runner.check_availability", side_effect=[[site_a], [site_b]])
    mocker.patch("core.runner.attempt_cart_add", return_value=False)
    mocker.patch("core.runner.decrypt_password", return_value="plaintext")
    mock_notify = mocker.patch("core.runner.notify")
    run_scan(scan_id, factory, settings)
    run_scan(scan_id, factory, settings)
    assert mock_notify.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv/bin/pytest tests/test_runner.py -v
```

Expected: New tests FAIL (runner not updated). `test_run_saves_result_notifies_and_marks_cart` will also FAIL because `ScanResult` now requires `last_seen_at` which the runner doesn't set yet.

- [ ] **Step 3: Update Transaction 1 in `core/runner.py`**

Replace the Transaction 1 `with get_db(session_factory) as db:` block:

```python
    with get_db(session_factory) as db:
        scan = (
            db.query(Scan)
            .options(joinedload(Scan.user))
            .filter(Scan.id == scan_id, Scan.status == "active", Scan.deleted_at.is_(None))
            .first()
        )
        if not scan:
            logger.warning("Scan %d not found, inactive, or deleted", scan_id)
            return
        run = ScanRun(scan_id=scan_id, started_at=_now())
        db.add(run)
        db.flush()
        run_id = run.id
        prev_run = (
            db.query(ScanRun)
            .filter(
                ScanRun.scan_id == scan_id,
                ScanRun.id != run_id,
                ScanRun.finished_at.isnot(None),
            )
            .order_by(ScanRun.started_at.desc())
            .first()
        )
        prev_run_started_at = prev_run.started_at if prev_run else None
        db.expunge_all()
```

- [ ] **Step 4: Replace Transaction 2 in `core/runner.py`**

Replace the entire Transaction 2 block (the `with get_db` that currently checks for duplicates and creates the `ScanResult`):

```python
            with get_db(session_factory) as db:
                now = _now()
                existing = (
                    db.query(ScanResult)
                    .filter(
                        ScanResult.scan_id == scan_id,
                        ScanResult.campsite_id == str(site.campsite_id),
                        ScanResult.booking_date == booking_date,
                    )
                    .first()
                )
                if existing:
                    old_last_seen = existing.last_seen_at
                    existing.last_seen_at = now
                    result_id = existing.id
                    if scan.notify_on_new_only:
                        if prev_run_started_at and old_last_seen >= prev_run_started_at:
                            continue
                else:
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
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                    db.add(result)
                    db.flush()
                    result_id = result.id
```

Note: `continue` inside the `with` block is safe — Python exits the context manager cleanly (committing the `last_seen_at` update) before moving to the next loop iteration.

- [ ] **Step 5: Run the full runner test suite**

```
.venv/bin/pytest tests/test_runner.py -v
```

Expected: All PASS.

- [ ] **Step 6: Run the full test suite**

```
.venv/bin/pytest tests/ -v
```

Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add core/runner.py tests/test_runner.py
git commit -m "feat: re-notify when campsite returns after absence using last_seen_at"
```

---

## Self-Review

### Spec coverage

| Requirement | Task |
|-------------|------|
| Track `last_seen_at` per `ScanResult` | Task 1 |
| `first_seen_at` preserved on existing rows (not reset on re-appearance) | Task 3 Step 4 — upsert only updates `last_seen_at` on existing rows |
| Absence detected via previous `ScanRun.started_at`, not a time threshold | Task 3 Steps 3–4 |
| `last_seen_at` advances even when notification is skipped | Task 3 Step 4 — `continue` fires after the `with` block commits |
| `notify_on_new_only=False` always notifies, unaffected | Task 3 Step 4 — absence detection is guarded by `if scan.notify_on_new_only` |
| Existing databases migrated with backfill | Task 2 |
| Migration is idempotent | Task 2 Step 1 (`test_migrate_db_is_idempotent`) |

### Placeholder scan

No TBDs, no "handle edge cases" stubs. All code blocks are complete and runnable.

### Type consistency

- `prev_run_started_at`: `Optional[datetime]` — the `prev_run_started_at and ...` guard in Task 3 Step 4 handles the `None` case correctly.
- `result_id`: `int` — set in both the `existing` and `else` branches before Transactions 3 and 4 use it.
- `last_seen_at`: declared as `Mapped[datetime]` (Task 1), set as `now = _now()` in the runner (Task 3).
- `migrate_db(engine)` — signature matches all three call sites (`main.py`, `cli.py`, tests).
