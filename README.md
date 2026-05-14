# CampBuddy

Self-hosted campsite availability monitor. Watches for cancellations across Recreation.gov, ReserveCalifornia, and 20+ other providers (via [camply](https://github.com/juftin/camply)), adds available sites to cart automatically, and notifies you via email or Telegram so you can complete payment in time.

## Prerequisites

- Python 3.11+
- Docker + Docker Compose (for deployment)
- A Gmail account with an [App Password](https://support.google.com/accounts/answer/185833) or any SMTP provider
- Optional: a Telegram bot token from [@BotFather](https://t.me/botfather)
- Optional: a Recreation.gov account (needed for add-to-cart automation; notify-only works without it)

---

## Quick Start (local)

```bash
git clone https://github.com/onurburak9/campbuddy && cd campbuddy

# CampBuddy requires a virtual environment (camply pins pydantic v1)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Paste the key into .env as ENCRYPTION_KEY, fill SMTP_* fields

# Seed example scans and start
mkdir -p data
python cli.py seed config/scans.yaml
python main.py    # starts scheduler — Ctrl+C to stop
```

---

## Try It Yourself — Component by Component

Each section below lets you test a different part of the system independently. All commands assume the venv is active (`source .venv/bin/activate`).

### 1. Run the test suite

```bash
pytest tests/ -v                    # 47 tests, should all pass
pytest tests/ --cov=core --cov=db --cov=config --cov-report=term-missing   # coverage report
```

### 2. Search for real campsites (Availability — M2)

The POC script hits the real Recreation.gov API:

```bash
python poc_search.py
```

This searches rec areas 1076 (Stanislaus NF) and 2991 for July 3–6, 3 consecutive nights. You'll see real available campsites with booking URLs.

To search different areas/dates, edit `poc_search.py` — or write your own:

```python
from datetime import date
from camply.containers import SearchWindow
from camply.search import SearchRecreationDotGov

sites = SearchRecreationDotGov(
    search_window=SearchWindow(start_date=date(2026, 8, 1), end_date=date(2026, 8, 5)),
    recreation_area=[2725],  # your rec area ID
    nights=2,
).get_matching_campsites(continuous=False)

for s in sites:
    print(f"  {s.facility_name} — {s.campsite_site_name}: {s.booking_url}")
```

**Finding recreation area IDs:** Search on [recreation.gov](https://www.recreation.gov), open a campground page, and look at the URL — e.g., `recreation.gov/camping/campgrounds/232447` gives you campground ID `232447`. For recreation *area* IDs, use `camply recreation-areas --search "Yosemite"`.

### 3. Test notifications (Notifications — M3)

CampBuddy delivers two kinds of notifications:

- **Urgent** — one immediate email/Telegram per cart-add success. The Recreation.gov cart hold is ~15 minutes; act quickly.
- **Digest** — one summary per scan run listing every available site that was *not* auto-carted (book manually). Sent once at the end of each run.

`python cli.py test-notify <scan_id>` sends a test notification using the urgent format.

First, ensure your `.env` has valid SMTP credentials. Then:

```bash
# Seed a scan if you haven't already
python cli.py seed config/scans.yaml

# Send a test notification for scan #1
python cli.py test-notify 1
```

This sends a fake "campsite found" notification to the email and/or Telegram configured on scan #1. Check your inbox / Telegram.

### 4. Exercise the database directly (Foundation — M1)

```bash
python -c "
from db.session import make_engine, create_tables, make_session_factory, get_db
from db.models import User, Scan, ScanRun, ScanResult

engine = make_engine('sqlite:///./data/campbuddy.db')
create_tables(engine)
factory = make_session_factory(engine)

with get_db(factory) as db:
    for s in db.query(Scan).all():
        runs = db.query(ScanRun).filter_by(scan_id=s.id).count()
        results = db.query(ScanResult).filter_by(scan_id=s.id).count()
        print(f'Scan {s.id}: {s.status.value}, {runs} runs, {results} results')
"
```

### 5. Manage scans via CLI (CLI — M6)

```bash
python cli.py list-scans            # show all scans
python cli.py pause 1               # pause scan #1
python cli.py list-scans            # verify it shows 'paused'
python cli.py resume 1              # resume it
python cli.py delete-scan 1 --yes   # delete scan + all history
python cli.py seed config/scans.yaml  # re-seed from YAML
```

### 6. Run the scheduler locally (Runner + Scheduler — M5)

```bash
python main.py
```

The scheduler starts and fires scans at their configured `polling_interval` (default 300s = 5 minutes). Watch the logs — you'll see:

```
INFO core.scheduler — Scheduled scan_1 every 300s
INFO core.scheduler — Scheduler started with 4 job(s)
INFO  CampBuddy running. SIGINT or SIGTERM to stop.
```

When a scan fires and finds availability, you'll see notification logs. Press Ctrl+C to stop.

**Note:** Without the Playwright sidecar running, cart-add will fail gracefully (you still get notified with the booking URL). To test with cart-add, use Docker Compose (see below).

---

## Docker Compose Deployment

Docker Compose runs two containers:
- **app** — the scheduler + runner + notifier
- **playwright** — isolated headless Chromium for add-to-cart automation

### Build and start

```bash
# Make sure .env is configured and scans are seeded
cp .env.example .env && vim .env
mkdir -p data
python cli.py seed config/scans.yaml    # seeds the SQLite DB locally

docker compose build                     # build both images
docker compose up -d                     # start in background
```

### Monitor

```bash
docker compose ps                        # container status + health
docker compose logs -f app               # live scheduler/scan logs
docker compose logs -f playwright        # Playwright sidecar logs
docker compose logs --since 1h app       # last hour of app logs
```

### Verify Playwright sidecar is running

```bash
curl http://localhost:8001/health        # should return {"status":"ok"}
# Note: port 8001 is exposed only on localhost for debugging.
# In production, only the app container talks to the sidecar via Docker networking.
```

### Update scans (no restart needed)

```bash
vim config/scans.yaml                    # edit your scans
python cli.py seed config/scans.yaml    # re-seed DB
# The scheduler auto-syncs every 60 seconds — new scans start automatically
```

### Stop / restart

```bash
docker compose down                      # stop and remove containers
docker compose restart app               # restart just the app
docker compose up -d --build             # rebuild and restart
```

### Backup the database

```bash
mkdir -p data/backups
cp data/campbuddy.db data/backups/campbuddy.db.$(date +%Y%m%d)
```

Add to crontab for automatic daily backups (keeps last 10):
```
0 3 * * 0 cp /path/to/campbuddy/data/campbuddy.db /path/to/campbuddy/data/backups/campbuddy.db.$(date +\%Y\%m\%d) && ls -t /path/to/campbuddy/data/backups/campbuddy.db.* | tail -n +11 | xargs rm -f
```

---

## Configuration Reference

### `config/scans.yaml`

```yaml
users:
  - email: you@example.com               # notification email
    telegram_chat_id: "123456789"         # from @userinfobot on Telegram (leave "" to disable)
    recreationgov_email: you@example.com  # for add-to-cart automation
    recreationgov_password: your-password  # encrypted at seed time

scans:
  - user_email: you@example.com           # must match a user above
    provider: RecreationDotGov            # camply provider name
    polling_interval: 300                 # seconds between checks (300 = 5 min)
    rec_area_ids: [1076, 2991]            # recreation area IDs (JSON array)
    campground_ids: null                  # alternative: specific campground IDs
    campsite_ids: null                    # alternative: exact campsite IDs
    search_windows:                       # one or more date ranges
      - start_date: "2026-07-03"
        end_date: "2026-07-06"
    nights: 3                             # consecutive nights required (1 = any single night)
    days_of_week: null                    # [0-6] Mon=0, Sun=6; null = any day
    weekends_only: false                  # only Fri/Sat nights
    notify_via_email: true
    notify_via_telegram: false
    notify_on_new_only: true              # suppress repeat alerts for same site+date
```

### Environment Variables (`.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENCRYPTION_KEY` | yes | — | Fernet key for encrypting Recreation.gov passwords |
| `SMTP_HOST` | no | smtp.gmail.com | SMTP server |
| `SMTP_PORT` | no | 587 | SMTP port |
| `SMTP_USER` | yes | — | SMTP login |
| `SMTP_PASSWORD` | yes | — | SMTP password / app password |
| `SMTP_FROM` | yes | — | From address in emails |
| `TELEGRAM_BOT_TOKEN` | no | — | Bot token from @BotFather (empty to disable) |
| `PLAYWRIGHT_SERVICE_URL` | no | http://playwright:8001 | Playwright sidecar URL |
| `DATABASE_URL` | no | sqlite:///./data/campbuddy.db | SQLite path |

---

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for system design, data flow, and component descriptions.
Key design decisions are documented as ADRs in [docs/adr/](docs/adr/).
