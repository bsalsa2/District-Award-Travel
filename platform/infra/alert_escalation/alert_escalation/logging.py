import logging
from pythonjsonlogger import jsonlogger
from .config import settings

def setup_logging():
    logger = logging.getLogger()

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create JSON formatter
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s %(funcName)s %(lineno)d'
    )

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Set log level based on environment
    log_level = logging.INFO
    if settings.DEBUG:
        log_level = logging.DEBUG

    logger.setLevel(log_level)

    return logger
