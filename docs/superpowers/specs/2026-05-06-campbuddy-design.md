# CampBuddy — Design Spec
**Date:** 2026-05-06

## Overview

CampBuddy is a self-hosted campsite availability monitor and booking assistant. It periodically checks campgrounds across 20+ providers (via camply), and when it finds a match it adds the site to the user's cart on Recreation.gov and notifies them via email and/or Telegram to complete payment.

Designed for a small group of users on a single VPS. Not a public SaaS — no billing, no onboarding flow, admin-controlled user registration.

---

## Goals

- Monitor campsite availability across multiple providers and date windows
- Add matching sites to cart automatically (Playwright), fall back to manual link if cart add fails
- Notify users via email and Telegram with direct booking URL in message body
- Store full run history — every execution recorded regardless of outcome
- Self-hosted on a VPS, deployed via Docker Compose
- Phase 1: config file + CLI; Phase 2: web dashboard; Phase 3: Telegram bot interface

## Non-Goals

- Completing the booking transaction (payment) — user does this manually
- Public user registration or billing
- Auto-booking without user confirmation

---

## Architecture

Single Python service. No microservices, no message queue.

```
campbuddy/
├── core/
│   ├── scheduler.py       # APScheduler — triggers scans per config
│   ├── availability.py    # Thin wrapper around camply OO API
│   ├── booking.py         # Playwright — adds campsite to cart
│   └── notifier.py        # Email (SMTP) + Telegram dispatch
├── db/
│   ├── models.py          # SQLAlchemy ORM models
│   └── session.py         # SQLite connection + session factory
├── config/
│   └── scans.yaml         # Phase 1: scan definitions
├── api/                   # Phase 2: FastAPI web dashboard
├── bot/                   # Phase 3: Telegram bot interface
└── main.py                # Entry point — starts scheduler + API server
```

**Tech stack:** Python 3.11, SQLite, SQLAlchemy, APScheduler, FastAPI, Playwright, camply 0.34+

---

## Deployment

Two Docker containers managed by Docker Compose on a single VPS.

```yaml
services:
  app:
    # FastAPI + APScheduler + camply + notifier
    volumes:
      - ./data/campbuddy.db:/app/data/campbuddy.db
      - ./.env:/app/.env
    restart: unless-stopped

  playwright:
    # Isolated browser automation service
    # Internal HTTP API: POST { booking_url, credentials } → { success, error }
    image: mcr.microsoft.com/playwright/python:latest
    restart: unless-stopped
```

Playwright runs as a separate container to isolate Chromium crashes from the scheduler. App communicates with it via an internal HTTP API.

**VPS file layout:**
```
campbuddy/
├── docker-compose.yml
├── .env                  # ENCRYPTION_KEY, SMTP creds, Telegram bot token
└── data/
    └── campbuddy.db      # SQLite — back up regularly
```

**Phase rollout (no infra changes between phases):**
- Phase 1: scans.yaml + CLI seed, scheduler runs, no web port exposed
- Phase 2: expose port 8000, add Nginx + basic auth
- Phase 3: add Telegram bot token to .env, bot module activates

---

## Data Model

### `users`
| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| email | str | contact address for email notifications |
| telegram_chat_id | str nullable | for Telegram notifications |
| recreationgov_email | str nullable | Recreation.gov login |
| recreationgov_password | str nullable | Fernet-encrypted (AES-128-CBC + HMAC), decrypted at runtime |
| created_at | datetime | |

`recreationgov_password` is Fernet-encrypted using `ENCRYPTION_KEY` from env (`cryptography` library). If the key is lost, passwords must be re-entered.

### `scans`
| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| user_id | int FK | |
| provider | str | e.g. `RecreationDotGov`, `ReserveCalifornia` |
| status | str | `active` \| `paused` \| `completed` |
| polling_interval | int | seconds between checks |
| rec_area_ids | JSON | list of rec area IDs, e.g. `[1076, 2991]` |
| campground_ids | JSON nullable | list of campground IDs |
| campsite_ids | JSON nullable | list of exact campsite IDs |
| search_windows | JSON | list of `{start_date, end_date}` — supports multiple windows |
| nights | int | consecutive nights required, default 1 |
| days_of_week | JSON nullable | list of ints 0–6 (0=Monday, 6=Sunday, Python weekday convention), null = any day |
| weekends_only | bool | default false |
| notify_via_email | bool | |
| notify_via_telegram | bool | |
| notify_on_new_only | bool | suppress repeat notifications for already-seen sites |
| created_at | datetime | |

`search_windows` supports camply's multiple date window syntax:
```json
[
  {"start_date": "2023-07-12", "end_date": "2023-07-13"},
  {"start_date": "2023-07-19", "end_date": "2023-07-20"}
]
```

### `scan_runs`
One record per execution — always written regardless of outcome.

| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| scan_id | int FK | |
| started_at | datetime | |
| finished_at | datetime | |
| outcome | str | `success` \| `no_results` \| `error` |
| sites_found | int | 0 on no_results or error |
| error_message | str nullable | populated when outcome=error |

### `scan_results`
One record per available site per run.

| Column | Type | Notes |
|---|---|---|
| id | int PK | |
| scan_run_id | int FK | |
| scan_id | int FK | denormalized for easier dedup queries |
| campsite_id | str | Recreation.gov campsite ID |
| facility_name | str | |
| site_name | str | |
| campsite_type | str | e.g. `STANDARD NONELECTRIC`, `RV NONELECTRIC` |
| booking_date | date | |
| booking_end_date | date | |
| booking_url | str | direct Recreation.gov URL |
| first_seen_at | datetime | timestamp of first run where this site appeared |
| cart_added | bool | default false |
| cart_added_at | datetime nullable | |
| notified | bool | default false |
| notified_at | datetime nullable | |

---

## Scan Execution Flow

```
APScheduler fires for scan S
  ↓
Build SearchWindow list from scan.search_windows
Call SearchRecreationDotGov(
    search_window=[SearchWindow(...)],
    recreation_area=scan.rec_area_ids,
    campgrounds=scan.campground_ids,
    campsites=scan.campsite_ids,
    nights=scan.nights,
    weekends_only=scan.weekends_only,
    days_of_the_week=scan.days_of_week
).get_matching_campsites(continuous=False)
  ↓
Write scan_run record (always)
  ↓
For each AvailableCampsite returned:
  If notify_on_new_only=true AND (campsite_id + booking_date) already in scan_results for this scan → skip
  Else:
    Save scan_result (cart_added=false, notified=false)
    POST to Playwright service { booking_url, recreationgov_email, recreationgov_password }
      → success: update cart_added=true, cart_added_at=now
      → failure: log error, proceed to notify anyway
    Send notifications per scan.notify_via_email / notify_via_telegram
    Update notified=true, notified_at=now
```

---

## Booking Automation (Playwright Service)

Internal HTTP API on the Playwright container. The app service calls it; it never exposes ports externally.

**Request:** `POST /add-to-cart`
```json
{
  "booking_url": "https://www.recreation.gov/camping/campsites/10357088",
  "email": "user@example.com",
  "password": "decrypted-password"
}
```

**Response:**
```json
{ "success": true }
{ "success": false, "error": "Login failed" }
```

Playwright flow: launch headless Chromium → navigate to booking URL → log in → add to cart → return result.

A failed add-to-cart is non-fatal — the user is still notified with the direct booking URL.

---

## Notifications

### Email
```
Subject: Campsite available — Union West - Union Reservoir [Jul 3–6]

Site:   Union West - Union Reservoir — Site 1 (STANDARD NONELECTRIC)
Dates:  Jul 3 – Jul 6 (3 nights)
Status: Added to cart — complete payment within ~15 min

Book here: https://www.recreation.gov/camping/campsites/10357088
```

If cart add failed:
```
Status: Could not add to cart automatically — book manually now

Book here: https://www.recreation.gov/camping/campsites/10357088
```

### Telegram
```
🏕 Campsite available!
Union West - Union Reservoir — Site 1
Jul 3 – Jul 6 (3 nights) · STANDARD NONELECTRIC

✅ Added to cart — complete payment within ~15 min
🔗 https://www.recreation.gov/camping/campsites/10357088
```

If cart add failed:
```
⚠️ Could not add to cart automatically — book manually now
🔗 https://www.recreation.gov/camping/campsites/10357088
```

Booking URL is always present in plain text in both channels regardless of cart status.

---

## Phased Rollout

### Phase 1 — Core engine
- SQLite + SQLAlchemy models
- APScheduler running scans from `scans.yaml` config
- camply OO API integration
- Playwright add-to-cart service
- Email + Telegram notifications
- Full run history in DB

### Phase 2 — Web dashboard
- FastAPI + Jinja2/HTMX
- Create/edit/pause/delete scans
- View scan run history and results
- User management
- Nginx + basic auth in front

### Phase 3 — Telegram bot
- Create and manage scans via chat commands
- Receive notifications in same Telegram thread
- Same FastAPI backend, bot module added
