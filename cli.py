import logging
from datetime import datetime, timedelta, timezone

import yaml
import click
from db.models import User, Scan
from db.session import make_engine, create_tables, make_session_factory, get_db
from config.settings import get_settings
from core.crypto import encrypt_password

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_RETENTION_DAYS = 180


def get_factory():
    get_settings.cache_clear()
    settings = get_settings()
    engine = make_engine(settings.database_url)
    create_tables(engine)
    return make_session_factory(engine), settings


def _active_scan(db, scan_id: int):
    """Return a non-deleted scan by id, or None."""
    return db.query(Scan).filter(Scan.id == scan_id, Scan.deleted_at.is_(None)).first()


@click.group()
def cli():
    """CampBuddy — campsite availability monitor."""


@cli.command()
@click.argument("yaml_path", default="config/scans.yaml")
def seed(yaml_path: str):
    """Seed users and scans from YAML. Safe to run multiple times."""
    factory, settings = get_factory()
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    with get_db(factory) as db:
        for u in data.get("users", []):
            user = db.query(User).filter(User.email == u["email"]).first()
            if not user:
                user = User(email=u["email"])
                db.add(user)
                db.flush()
                logger.info("Created user %s", u["email"])
            if u.get("telegram_chat_id"):
                user.telegram_chat_id = str(u["telegram_chat_id"])
            if u.get("recreationgov_email"):
                user.recreationgov_email = u["recreationgov_email"]
            if u.get("recreationgov_password"):
                user.recreationgov_password = encrypt_password(
                    str(u["recreationgov_password"]), settings.encryption_key
                )
        db.flush()

        for s in data.get("scans", []):
            user = db.query(User).filter(User.email == s["user_email"]).first()
            if not user:
                logger.error("User %s not found — skipping scan", s["user_email"])
                continue
            scan = Scan(
                name=s.get("name"),
                user_id=user.id,
                provider=s.get("provider", "RecreationDotGov"),
                polling_interval=s.get("polling_interval", 300),
                rec_area_ids=s.get("rec_area_ids"),
                campground_ids=s.get("campground_ids"),
                campsite_ids=s.get("campsite_ids"),
                search_windows=s["search_windows"],
                nights=s.get("nights", 1),
                days_of_week=s.get("days_of_week"),
                weekends_only=s.get("weekends_only", False),
                notify_via_email=s.get("notify_via_email", True),
                notify_via_telegram=s.get("notify_via_telegram", False),
                notify_on_new_only=s.get("notify_on_new_only", True),
            )
            db.add(scan)
            logger.info("Added scan for %s (%s)", s["user_email"], s.get("provider", "RecreationDotGov"))

    click.echo("Seed complete.")


@cli.command("list-scans")
def list_scans():
    """List all active (non-deleted) scans and their current status."""
    factory, _ = get_factory()
    with get_db(factory) as db:
        scans = db.query(Scan).join(User).filter(Scan.deleted_at.is_(None)).all()
        if not scans:
            click.echo("No scans found.")
            return
        for s in scans:
            windows = len(s.search_windows)
            label = f" ({s.name})" if s.name else ""
            click.echo(
                f"[{s.id:3}]{label} {s.status.value:9} | {s.user.email:30} | {s.provider:20} | "
                f"interval={s.polling_interval}s | {windows} window(s)"
            )


@cli.command()
@click.argument("scan_id", type=int)
def pause(scan_id: int):
    """Pause an active scan."""
    factory, _ = get_factory()
    with get_db(factory) as db:
        scan = _active_scan(db, scan_id)
        if not scan:
            click.echo(f"Scan {scan_id} not found.")
            return
        scan.status = "paused"
    click.echo(f"Scan {scan_id} paused.")


@cli.command()
@click.argument("scan_id", type=int)
def resume(scan_id: int):
    """Resume a paused scan."""
    factory, _ = get_factory()
    with get_db(factory) as db:
        scan = _active_scan(db, scan_id)
        if not scan:
            click.echo(f"Scan {scan_id} not found.")
            return
        scan.status = "active"
    click.echo(f"Scan {scan_id} resumed.")


@cli.command("delete-scan")
@click.argument("scan_id", type=int)
@click.confirmation_option(prompt="Soft-delete scan? (history kept for 180 days)")
def delete_scan(scan_id: int):
    """Soft-delete a scan. Run history is retained for 180 days then pruned."""
    factory, _ = get_factory()
    with get_db(factory) as db:
        scan = _active_scan(db, scan_id)
        if not scan:
            click.echo(f"Scan {scan_id} not found.")
            return
        scan.deleted_at = datetime.now(timezone.utc)
    click.echo(f"Scan {scan_id} deleted (history retained for {_RETENTION_DAYS} days).")


@cli.command("prune-scans")
def prune_scans():
    """Hard-delete scans (and their history) that were soft-deleted over 180 days ago."""
    factory, _ = get_factory()
    cutoff = datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)
    with get_db(factory) as db:
        expired = (
            db.query(Scan)
            .filter(Scan.deleted_at.isnot(None), Scan.deleted_at < cutoff)
            .all()
        )
        if not expired:
            click.echo("No expired scans to prune.")
            return
        for scan in expired:
            db.delete(scan)
        click.echo(f"Pruned {len(expired)} expired scan(s).")


@cli.command("test-notify")
@click.argument("scan_id", type=int)
def test_notify(scan_id: int):
    """Send a test notification for a scan."""
    from datetime import date
    from core.notifier import notify, NotificationPayload
    factory, settings = get_factory()
    with get_db(factory) as db:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            click.echo(f"Scan {scan_id} not found.")
            return
        payload = NotificationPayload(
            facility_name="TEST — Upper Pines Campground",
            site_name="42",
            campsite_type="STANDARD NONELECTRIC",
            booking_date=date(2026, 7, 4),
            booking_end_date=date(2026, 7, 7),
            booking_url="https://www.recreation.gov/camping/campsites/99999",
            cart_added=False,
            nights=3,
        )
        notify(scan, payload, settings)
    click.echo("Test notification sent.")


@cli.command("test-cart")
@click.argument("scan_id", type=int)
@click.argument("booking_url")
@click.argument("check_in")
@click.argument("check_out")
def test_cart(scan_id: int, booking_url: str, check_in: str, check_out: str):
    """Trigger an add-to-cart attempt via the Playwright service for a given scan's credentials."""
    import requests
    from core.crypto import decrypt_password
    factory, settings = get_factory()
    with get_db(factory) as db:
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            click.echo(f"Scan {scan_id} not found.")
            return
        user = scan.user
        if not user.recreationgov_email or not user.recreationgov_password:
            click.echo("User has no Recreation.gov credentials stored.")
            return
        email = user.recreationgov_email
        password = decrypt_password(user.recreationgov_password, settings.encryption_key)

    playwright_url = settings.playwright_service_url
    click.echo(f"Calling {playwright_url}/add-to-cart ...")
    resp = requests.post(
        f"{playwright_url}/add-to-cart",
        json={"booking_url": booking_url, "email": email, "password": password, "check_in": check_in, "check_out": check_out},
        timeout=120,
    )
    click.echo(f"Status: {resp.status_code}")
    click.echo(resp.json())


@cli.command("update-user")
@click.argument("user_id", type=int)
@click.option("--email", default=None, help="New login email address.")
@click.option("--recreationgov-email", default=None, help="Recreation.gov account email.")
@click.option("--recreationgov-password", default=None, help="Recreation.gov password (will be encrypted).")
@click.option("--clear-password", is_flag=True, help="Remove stored Recreation.gov password.")
@click.option("--telegram-chat-id", default=None, help="Telegram chat ID.")
@click.option("--password", default=None, help="Web UI login password (will be hashed).")
@click.option("--scan-limit", default=None, type=int, help="Maximum number of active scans.")
def update_user(user_id, email, recreationgov_email, recreationgov_password, clear_password, telegram_chat_id, password, scan_limit):
    """Update fields on a user row."""
    import bcrypt
    factory, settings = get_factory()
    with get_db(factory) as db:
        user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
        if not user:
            click.echo(f"User {user_id} not found.")
            return
        if email:
            user.email = email
        if recreationgov_email:
            user.recreationgov_email = recreationgov_email
        if recreationgov_password:
            user.recreationgov_password = encrypt_password(recreationgov_password, settings.encryption_key)
        if clear_password:
            user.recreationgov_password = None
        if telegram_chat_id:
            user.telegram_chat_id = telegram_chat_id
        if password:
            user.hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        if scan_limit is not None:
            user.scan_limit = scan_limit
        click.echo(f"User {user_id} updated: email={user.email} rec_email={user.recreationgov_email} "
                   f"password={'set' if user.recreationgov_password else 'none'} "
                   f"telegram={user.telegram_chat_id} "
                   f"scan_limit={user.scan_limit}")


@cli.command("set-password")
@click.argument("email")
@click.option("--password", default=None, help="New login password. If omitted, a secure prompt is shown.")
def set_password(email: str, password: str):
    """Set (or reset) the web UI login password for a user identified by EMAIL."""
    from api.auth import hash_password
    if password is None:
        password = click.prompt("New password", hide_input=True, confirmation_prompt=True)
    factory, _ = get_factory()
    with get_db(factory) as db:
        user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
        if not user:
            click.echo(f"Error: User '{email}' not found.")
            raise SystemExit(1)
        user.hashed_password = hash_password(password)
    click.echo(f"Password set for {email}.")


@cli.command("change-password")
@click.argument("email")
@click.option("--current-password", default=None, help="Current login password.")
@click.option("--new-password", default=None, help="New login password.")
def change_password(email: str, current_password: str, new_password: str):
    """Change the web UI login password for EMAIL, requiring the current password first."""
    from api.auth import hash_password, verify_password
    if current_password is None:
        current_password = click.prompt("Current password", hide_input=True)
    factory, _ = get_factory()
    with get_db(factory) as db:
        user = db.query(User).filter(User.email == email, User.deleted_at.is_(None)).first()
        if not user:
            click.echo(f"Error: User '{email}' not found.")
            raise SystemExit(1)
        if not user.hashed_password:
            click.echo(f"Error: User '{email}' has no password set. Use set-password instead.")
            raise SystemExit(1)
        if not verify_password(current_password, user.hashed_password):
            click.echo("Error: Current password is incorrect.")
            raise SystemExit(1)
        if new_password is None:
            new_password = click.prompt("New password", hide_input=True, confirmation_prompt=True)
        user.hashed_password = hash_password(new_password)
    click.echo(f"Password changed for {email}.")


@cli.command("delete-user")
@click.argument("user_id", type=int)
@click.confirmation_option(prompt="Soft-delete user and their scans? (history kept for 180 days)")
def delete_user(user_id: int):
    """Soft-delete a user and all their scans. History is retained for 180 days."""
    factory, _ = get_factory()
    now = datetime.now(timezone.utc)
    with get_db(factory) as db:
        user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
        if not user:
            click.echo(f"User {user_id} not found.")
            return
        user.deleted_at = now
        db.query(Scan).filter(
            Scan.user_id == user_id, Scan.deleted_at.is_(None)
        ).update({"deleted_at": now})
    click.echo(f"User {user_id} deleted (history retained for {_RETENTION_DAYS} days).")


if __name__ == "__main__":
    cli()
