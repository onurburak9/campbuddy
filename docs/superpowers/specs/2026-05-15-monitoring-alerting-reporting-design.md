# Monitoring, Alerting & Daily Reporting

**Date:** 2026-05-15
**Branch:** `feature/monitoring-alerting-reporting`
**Status:** Design

## Problem

CampBuddy has no application-level observability. The only way to know whether scans are running correctly is to manually check logs in Grafana. If a scan stalls, errors repeatedly, or the scheduler falls behind, nobody is notified. There's also no health endpoint on the main app container (only the Playwright sidecar has one), meaning Docker can't auto-restart it on failure.

## Goals

1. **Alerts** — Detect and notify on scan runner problems in near real-time (error streaks, stalled scans).
2. **Daily digest** — Send a summary report every morning with system-wide stats.
3. **Health endpoint** — Expose `/health` so Docker can healthcheck the app container and Grafana can confirm the process is alive.

## Non-Goals

- Prometheus/StatsD custom metrics instrumentation (Grafana already covers container-level metrics via `up{}`, `container_last_seen{}`).
- External error tracking (Sentry, etc.).
- Per-user reporting (this is admin-level observability).

---

## Architecture

### New module: `core/monitor.py`

A single module containing all monitoring logic. It registers two jobs on the existing APScheduler in `core/scheduler.py`:

| Job | Schedule | Purpose |
|-----|----------|---------|
| `__watchdog__` | Every 5 minutes | Detect error streaks and stalled scans, send alerts |
| `__daily_digest__` | Once daily at 08:00 local | Send system summary via email + Telegram |

### New module: `core/health.py`

A minimal HTTP server (stdlib `http.server`) running in a daemon thread on port 8000. Single endpoint:

| Endpoint | Response |
|----------|----------|
| `GET /health` | `{"status": "ok", "scheduler_running": true, "active_scans": 5, "last_watchdog": "2026-05-15T08:00:00Z"}` |

Using stdlib avoids adding Flask/FastAPI as a dependency to the main process. The health server is started from `main.py` alongside the scheduler.

### New settings in `config/settings.py`

| Setting | Env Var | Default | Description |
|---------|---------|---------|-------------|
| `timezone` | `TIMEZONE` | `"UTC"` | Local timezone for daily digest scheduling (e.g., `"America/Los_Angeles"`) |
| `admin_email` | `ADMIN_EMAIL` | `""` | Email recipient for alerts and daily digest. If empty, falls back to `smtp_from`. |
| `admin_telegram_chat_id` | `ADMIN_TELEGRAM_CHAT_ID` | `""` | Telegram chat ID for admin alerts/reports. If empty, Telegram alerts are skipped. |
| `health_port` | `HEALTH_PORT` | `8000` | Port for the `/health` endpoint |

### Changes to existing files

| File | Change |
|------|--------|
| `core/scheduler.py` | `start_scheduler()` registers `__watchdog__` and `__daily_digest__` jobs |
| `main.py` | Starts health server thread before scheduler |
| `config/settings.py` | Adds 4 new settings fields |
| `docker-compose.yml` | Adds healthcheck for `app` service on port 8000 |
| `.env.example` | Documents new env vars |

---

## Watchdog: Error Detection

The watchdog job runs every 5 minutes and checks two conditions per active scan:

### 1. Error Streaks

Query: get the last N runs for each active scan. If the last `CONSECUTIVE_FAILURE_THRESHOLD` (default: 3) runs all have `outcome="error"`, fire an alert.

```sql
SELECT scan_id, outcome FROM scan_runs
WHERE scan_id = :id
ORDER BY started_at DESC LIMIT 3
```

### 2. Stall Detection

For each active scan, check if the time since its last `ScanRun.started_at` exceeds `2 × scan.polling_interval`. If so, the scan is considered stalled (the scheduler missed it or the job is hung).

```sql
SELECT MAX(started_at) FROM scan_runs WHERE scan_id = :id
```

Compare: `now() - last_started_at > 2 * scan.polling_interval`

### Alert Cooldown

In-memory dict tracking `{scan_id: last_alert_time}`. A new alert for the same scan is suppressed if less than 1 hour has passed since the last alert. The cooldown dict resets on process restart (acceptable — worst case is one duplicate alert after restart).

### Alert Format

**Email subject:** `[CampBuddy Alert] Scan "{name}" — {error_type}`

**Email/Telegram body:**
```
⚠️ Scan Alert: {scan.name} (ID: {scan.id})
Problem: {description}
Last run: {last_run.started_at}
Last error: {last_run.error_message or "N/A"}
Owner: {user.email}
```

Where `{description}` is one of:
- "3 consecutive failures" (with the error message from the most recent run)
- "No runs in {elapsed} (expected every {polling_interval}s)"

---

## Daily Digest

Runs once at 08:00 in the configured timezone. Queries the last 24 hours of data.

### Metrics Collected

| Metric | Query |
|--------|-------|
| Total users | `COUNT(users) WHERE deleted_at IS NULL` |
| Active scans | `COUNT(scans) WHERE status='active' AND deleted_at IS NULL` |
| Paused scans | `COUNT(scans) WHERE status='paused' AND deleted_at IS NULL` |
| Total runs (24h) | `COUNT(scan_runs) WHERE started_at > now - 24h` |
| Successful runs | `COUNT WHERE outcome='success'` |
| No-result runs | `COUNT WHERE outcome='no_results'` |
| Error runs | `COUNT WHERE outcome='error'` |
| Error rate | `error_runs / total_runs * 100` |
| Sites found (24h) | `SUM(sites_found) WHERE started_at > now - 24h` |
| Cart adds (24h) | `COUNT(scan_results) WHERE cart_added=True AND cart_added_at > now - 24h` |
| Notifications sent (24h) | `COUNT(scan_results) WHERE notified=True AND notified_at > now - 24h` |
| Currently stalled scans | Same stall detection query as watchdog |
| Currently failing scans | Same error streak query as watchdog |

### Report Format

**Email subject:** `[CampBuddy] Daily Report — {date}`

**Body (plain text, same for email and Telegram):**
```
📊 CampBuddy Daily Report — May 15, 2026

Users:         3
Active scans:  5 | Paused: 2

Runs (24h):    120
  ✅ Success:    85 (70.8%)
  ➖ No results: 30 (25.0%)
  ❌ Errors:      5 (4.2%)

Sites found:   12
Cart adds:      8
Notifications: 12

⚠️ Alerts:
  • Scan "Yosemite Weekends" — 3 consecutive failures
  • Scan "Joshua Tree" — stalled (no run in 25 min, expected every 10 min)

All clear ✅  (if no alerts)
```

---

## Health Endpoint

### `GET /health` (port 8000)

Returns JSON with current system state. Used by Docker healthcheck and optionally by Grafana.

```json
{
  "status": "ok",
  "uptime_seconds": 86400,
  "scheduler_running": true,
  "active_scans": 5,
  "scheduled_jobs": 7,
  "last_watchdog_run": "2026-05-15T15:00:00Z",
  "version": "1.0.0"
}

```

**Status logic:**
- `"ok"` — scheduler is running and watchdog ran within the last 10 minutes
- `"degraded"` — scheduler is running but watchdog hasn't run recently
- `"error"` — scheduler is not running

**Docker healthcheck** (added to `docker-compose.yml`):
```yaml
app:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 5s
    retries: 3
```

The health server stores a reference to the scheduler (passed at startup) to inspect job state. It also tracks `last_watchdog_run` via a module-level timestamp updated by the watchdog job.

---

## Notification Helpers

The existing `core/notifier.py` is designed around `NotificationPayload` (campsite availability). Rather than overloading that interface, `core/monitor.py` will have its own lightweight send functions:

- `_send_admin_email(subject: str, body: str, settings)` — uses the same `smtplib` pattern as `notifier.send_email`, sends to `admin_email`.
- `_send_admin_telegram(body: str, settings)` — uses the same `requests.post` pattern, sends to `admin_telegram_chat_id`.
- `_send_admin_notification(subject: str, body: str, settings)` — dispatches to both, catching errors independently.

This avoids coupling the monitor to the scan-specific `NotificationPayload` dataclass.

---

## Testing Strategy

All tests use in-memory SQLite and mock I/O, following existing conventions.

### `tests/test_monitor.py`

| Test | What it verifies |
|------|------------------|
| `test_watchdog_detects_error_streak` | 3 consecutive error runs → alert sent |
| `test_watchdog_no_alert_below_threshold` | 2 errors then 1 success → no alert |
| `test_watchdog_detects_stall` | No run in 2× polling_interval → alert sent |
| `test_watchdog_cooldown` | Second alert within 1 hour → suppressed |
| `test_watchdog_cooldown_expired` | Alert after 1 hour → sent again |
| `test_daily_digest_content` | Report contains correct counts from seeded data |
| `test_daily_digest_empty_db` | No runs → report shows zeros, no crash |
| `test_admin_email_sent` | Alert dispatches email with correct subject/body |
| `test_admin_telegram_sent` | Alert dispatches Telegram message |
| `test_admin_telegram_skipped` | Empty `admin_telegram_chat_id` → no Telegram call |

### `tests/test_health.py`

| Test | What it verifies |
|------|------------------|
| `test_health_ok` | Running scheduler + recent watchdog → `status: ok` |
| `test_health_degraded` | Running scheduler + stale watchdog → `status: degraded` |
| `test_health_returns_json` | Response is valid JSON with expected keys |

---

## File Summary

| File | Action | Lines (est.) |
|------|--------|-------------|
| `core/monitor.py` | **New** | ~150 |
| `core/health.py` | **New** | ~60 |
| `config/settings.py` | Modify | +6 lines |
| `core/scheduler.py` | Modify | +15 lines |
| `main.py` | Modify | +5 lines |
| `docker-compose.yml` | Modify | +5 lines |
| `.env.example` | Modify | +4 lines |
| `tests/test_monitor.py` | **New** | ~200 |
| `tests/test_health.py` | **New** | ~60 |
