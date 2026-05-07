# CampBuddy

Self-hosted campsite availability monitor. Watches for cancellations across Recreation.gov, ReserveCalifornia, and 20+ other providers (via [camply](https://github.com/juftin/camply)), adds available sites to cart automatically, and notifies you via email or Telegram so you can complete payment in time.

## Prerequisites

- Python 3.11+
- Docker + Docker Compose (for VPS deployment)
- A Gmail account with an [App Password](https://support.google.com/accounts/answer/185833) (recommended for SMTP), or any other SMTP provider
- Optional: a Telegram bot token from [@BotFather](https://t.me/botfather)
- A Recreation.gov account (only required if you want add-to-cart automation; notify-only works without it)

## Setup (local development)

CampBuddy depends on pydantic v1 (because camply does), so it must run in an isolated virtual environment.

```bash
git clone https://github.com/onurburak9/campbuddy
cd campbuddy

# 1. Create venv and install
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Generate ENCRYPTION_KEY:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Edit .env — paste the key, fill SMTP credentials, optionally TELEGRAM_BOT_TOKEN

# 3. Seed scans + run
mkdir -p data
python cli.py seed config/scans.yaml
python main.py
```

## Configuration

Edit `config/scans.yaml` to define users and scans:

```yaml
users:
  - email: you@example.com
    telegram_chat_id: "123456789"
    recreationgov_email: you@example.com
    recreationgov_password: your-plaintext-password   # encrypted at seed time

scans:
  - user_email: you@example.com
    provider: RecreationDotGov
    polling_interval: 300          # check every 5 minutes
    rec_area_ids: [1076, 2991]
    search_windows:
      - start_date: "2026-07-03"
        end_date: "2026-07-06"
    nights: 3
    notify_via_email: true
    notify_via_telegram: false
    notify_on_new_only: true       # suppress repeat alerts for same site+date
```

Re-seed after changes: `python cli.py seed config/scans.yaml`

The scheduler picks up new scans within 60 seconds — no restart needed.

## Deployment (VPS via Docker Compose)

```bash
# On your VPS
git clone https://github.com/onurburak9/campbuddy && cd campbuddy
cp .env.example .env && vim .env
mkdir -p data
python cli.py seed config/scans.yaml
docker compose up -d
docker compose logs -f
```

## Managing Scans

```bash
python cli.py list-scans          # show all scans
python cli.py pause <id>          # pause without deleting
python cli.py resume <id>         # re-activate
python cli.py delete-scan <id>    # remove scan + all history
python cli.py test-notify <id>    # send a test notification to verify channels
```

## Testing

```bash
# Activate venv first
pytest tests/ -v
pytest tests/ --cov=core --cov=db --cov-report=term-missing
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for system design, data flow, and component descriptions.  
Key design decisions are documented as ADRs in [docs/adr/](docs/adr/).
