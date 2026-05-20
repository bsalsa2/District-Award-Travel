import os
import time
import json
import logging
from logging.handlers import RotatingFileHandler
import redis
import requests
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory()
)

logger = structlog.get_logger()

# Redis client
redis_client = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379/0'))

# Notification service URL
NOTIFICATION_SERVICE_URL = os.getenv('NOTIFICATION_SERVICE_URL', 'http://notification-service:8080')

def process_alert_queue():
    """Process alerts from Redis queue"""
    logger.info("Notification worker started")

    while True:
        try:
            # Blocking pop from Redis list
            _, alert_data = redis_client.blpop('alert:queue', timeout=30)

            if alert_data:
                alert_data = json.loads(alert_data.decode('utf-8'))
                logger.info("Processing alert from queue", alert_id=alert_data['id'])

                # Forward to notification service
                response = requests.post(
                    f"{NOTIFICATION_SERVICE_URL}/api/v1/alerts",
                    json=alert_data,
                    timeout=10
                )

                if response.status_code == 202:
                    logger.info("Alert forwarded to notification service", alert_id=alert_data['id'])
                else:
                    logger.error("Failed to forward alert",
                                alert_id=alert_data['id'],
                                status_code=response.status_code)
                    # Requeue the alert
                    redis_client.rpush('alert:queue', json.dumps(alert_data))

        except redis.ConnectionError:
            logger.error("Redis connection error, retrying in 5 seconds")
            time.sleep(5)
        except Exception as e:
            logger.error("Error processing alert", error=str(e))
            time.sleep(5)

if __name__ == '__main__':
    # Set up logging
    handler = RotatingFileHandler(
        '/var/log/notification-worker/worker.log',
        maxBytes=10485760,
        backupCount=5
    )
    handler.setLevel(logging.INFO)

    # Run the worker
    process_alert_queue()
