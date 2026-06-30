import sys
import io
import logging
from src.orchestrator import run_pipeline

# Force UTF-8 output on Windows to handle special characters in Claude responses
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log", encoding="utf-8")
    ]
)

logger = logging.getLogger("main")

def main():
    logger.info("Starting Cyber Security Job Aggregator CLI...")
    try:
        success = run_pipeline()
        if success:
            logger.info("Aggregator run completed successfully.")
            sys.exit(0)
        else:
            logger.error("Aggregator run completed with errors.")
            sys.exit(1)
    except Exception as e:
        logger.critical(f"Unhandled exception in pipeline: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
