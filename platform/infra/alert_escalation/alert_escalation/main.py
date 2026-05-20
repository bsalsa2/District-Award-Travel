import logging
import uvicorn
from .api import app
from .config import settings

def main():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting Alert Escalation API")

    # Run the FastAPI application
    uvicorn.run(
        "alert_escalation.api:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
        workers=4
    )

if __name__ == "__main__":
    main()
