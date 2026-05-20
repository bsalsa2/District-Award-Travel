import logging
import sys
from typing import Optional
from pythonjsonlogger import jsonlogger
from config import config

class JSONFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record['environment'] = config.environment
        log_record['service'] = getattr(record, 'service', 'unknown')

def setup_logging(service_name: str, log_level: Optional[str] = None) -> logging.Logger:
    """Configure structured logging for the service."""
    level = log_level or config.monitoring.log_level
    logger = logging.getLogger(service_name)
    logger.setLevel(level)

    # Remove existing handlers to avoid duplication
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create JSON formatter
    formatter = JSONFormatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s %(service)s %(environment)s'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    file_handler = logging.FileHandler(f'/app/logs/{service_name}.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# Global logger instance
logger = setup_logging('award-travel-engine')
