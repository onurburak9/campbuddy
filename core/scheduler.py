import logging
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from core.runner import run_scan

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


def build_scheduler() -> BackgroundScheduler:
    return BackgroundScheduler(timezone="UTC")


def _add_scan_job(scheduler, scan, session_factory, settings, immediate: bool) -> None:
    job_id = f"scan_{scan.id}"
    kwargs = dict(
        trigger=IntervalTrigger(seconds=scan.polling_interval),
        id=job_id,
        args=[scan.id, session_factory, settings],
        max_instances=1,
        coalesce=True,
    )
    if immediate:
        kwargs["next_run_time"] = _now()
    scheduler.add_job(run_scan, **kwargs)
    logger.info(
        "Scheduled %s every %ds%s", job_id, scan.polling_interval,
        " (immediate first run)" if immediate else "",
    )


def sync_jobs(scheduler: BackgroundScheduler, session_factory, settings) -> None:
    from db.models import Scan, ScanRun
    with session_factory() as db:
        active = db.query(Scan).filter(Scan.status == "active", Scan.deleted_at.is_(None)).all()
        active_ids = {f"scan_{s.id}" for s in active}
        active_map = {f"scan_{s.id}": s for s in active}
        scan_ids_with_runs = {
            row[0] for row in db.query(ScanRun.scan_id)
            .filter(ScanRun.scan_id.in_([s.id for s in active]))
            .distinct()
            .all()
        }

    existing_jobs = {job.id: job for job in scheduler.get_jobs() if job.id.startswith("scan_")}
    existing_ids = set(existing_jobs)

    for job_id in existing_ids - active_ids:
        scheduler.remove_job(job_id)
        logger.info("Removed job %s", job_id)

    for job_id in active_ids - existing_ids:
        scan = active_map[job_id]
        never_run = scan.id not in scan_ids_with_runs
        _add_scan_job(scheduler, scan, session_factory, settings, immediate=never_run)

    for job_id in active_ids & existing_ids:
        scan = active_map[job_id]
        job = existing_jobs[job_id]
        if job.trigger.interval.total_seconds() != scan.polling_interval:
            scheduler.remove_job(job_id)
            never_run = scan.id not in scan_ids_with_runs
            _add_scan_job(scheduler, scan, session_factory, settings, immediate=never_run)
            logger.info("Rescheduled %s: interval changed to %ds", job_id, scan.polling_interval)


def start_scheduler(session_factory, settings) -> BackgroundScheduler:
    scheduler = build_scheduler()
    sync_jobs(scheduler, session_factory, settings)
    scheduler.add_job(
        sync_jobs,
        trigger=IntervalTrigger(seconds=30),
        id="__sync_jobs__",
        args=[scheduler, session_factory, settings],
    )
    scheduler.start()
    logger.info("Scheduler started with %d job(s)", len(scheduler.get_jobs()))
    return scheduler
