import logging
from datetime import datetime
from .engine import EscalationEngine
from .storage import AlertStorage
from .config import settings
import time
import signal
import sys

logger = logging.getLogger(__name__)

class EscalationWorker:
    def __init__(self):
        self.engine = EscalationEngine()
        self.storage = AlertStorage()
        self.running = True

    def handle_signal(self, signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def run(self):
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

        logger.info("Starting escalation worker")

        while self.running:
            try:
                # Process all active alerts
                alerts = self.storage.list_active_alerts()
                processed_count = 0

                for alert in alerts:
                    state = self.storage.get_escalation_state(alert.alert_id)
                    if state:
                        events = self.engine.perform_escalation(state)
                        if events:
                            logger.info(
                                f"Performed {len(events)} escalations for alert {alert.alert_id}"
                            )
                            processed_count += 1

                # Clean up old alerts
                cleaned = self.storage.cleanup_resolved_alerts()
                if cleaned > 0:
                    logger.info(f"Cleaned up {cleaned} resolved alerts")

                # Sleep for a while
                time.sleep(60)

            except Exception as e:
                logger.error(f"Error in escalation worker: {e}")
                time.sleep(10)

def main():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

    worker = EscalationWorker()
    worker.run()

if __name__ == "__main__":
    main()
