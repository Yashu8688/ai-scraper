import sys
import io
import logging
from src.personal_orchestrator import run_personal_pipeline

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("personal_pipeline.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger("personal_main")


def main():
    logger.info("Starting Personal Job Aggregator (Hyderabad)...")
    try:
        success = run_personal_pipeline()
        if success:
            logger.info("Personal pipeline completed successfully.")
            sys.exit(0)
        else:
            logger.error("Personal pipeline completed with errors.")
            sys.exit(1)
    except Exception as e:
        logger.critical(f"Unhandled exception: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
