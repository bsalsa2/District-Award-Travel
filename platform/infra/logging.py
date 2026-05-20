import logging
import logging.handlers

# Create a logger
logger = logging.getLogger('district-award-travel')
logger.setLevel(logging.INFO)

# Create a rotating file handler
file_handler = logging.handlers.RotatingFileHandler('logs/monitoring_dashboard.log', maxBytes=1000000, backupCount=5)
file_handler.setLevel(logging.INFO)

# Create a console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create a formatter and attach it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

def log_message(message):
    logger.info(message)
