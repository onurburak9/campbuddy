import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from core.runner import run_scan

logger = logging.getLogger(__name__)


def build_scheduler() -> BackgroundScheduler:
    return BackgroundScheduler(timezone="UTC")


def sync_jobs(scheduler: BackgroundScheduler, session_factory, settings) -> None:
    from db.models import Scan
    with session_factory() as db:
        active = db.query(Scan).filter(Scan.status == "active", Scan.deleted_at.is_(None)).all()
        active_ids = {f"scan_{s.id}" for s in active}
        active_map = {f"scan_{s.id}": s for s in active}

    existing_ids = {job.id for job in scheduler.get_jobs() if job.id.startswith("scan_")}

    for job_id in existing_ids - active_ids:
        scheduler.remove_job(job_id)
        logger.info("Removed job %s", job_id)

    for job_id in active_ids - existing_ids:
        scan = active_map[job_id]
        scheduler.add_job(
            run_scan,
            trigger=IntervalTrigger(seconds=scan.polling_interval),
            id=job_id,
            args=[scan.id, session_factory, settings],
            max_instances=1,
            coalesce=True,
        )
        logger.info("Scheduled %s every %ds", job_id, scan.polling_interval)


def start_scheduler(session_factory, settings) -> BackgroundScheduler:
    scheduler = build_scheduler()
    sync_jobs(scheduler, session_factory, settings)
    scheduler.add_job(
        sync_jobs,
        trigger=IntervalTrigger(seconds=60),
        id="__sync_jobs__",
        args=[scheduler, session_factory, settings],
    )
    scheduler.start()
    logger.info("Scheduler started with %d job(s)", len(scheduler.get_jobs()))
    return scheduler
