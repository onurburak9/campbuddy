import logging
import signal
import sys
import time
from db.session import make_engine, create_tables, make_session_factory
from core.scheduler import start_scheduler
from config.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    create_tables(engine)
    session_factory = make_session_factory(engine)

    scheduler = start_scheduler(session_factory, settings)

    def _shutdown(sig, _frame):
        logger.info("Shutting down (signal %d)...", sig)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("CampBuddy running. SIGINT or SIGTERM to stop.")
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
