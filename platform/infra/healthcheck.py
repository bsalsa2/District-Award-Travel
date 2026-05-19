import logging
import subprocess
import os
import time
from datetime import datetime

# Set up logging
logging.basicConfig(filename='logs/healthcheck.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_fastapi_server():
    try:
        subprocess.check_output(['curl', '-s', '-f', 'http://localhost:8000/health'])
        logging.info('FastAPI server is running and responding to health checks')
        return True
    except subprocess.CalledProcessError:
        logging.error('FastAPI server is not running or not responding to health checks')
        return False

def check_database_file():
    db_file = '/home/runner/work/District-Award-Travel/District-Award-Travel/platform/db/award_travel.db'
    if os.path.exists(db_file) and os.access(db_file, os.W_OK):
        logging.info('Database file exists and is writable')
        return True
    else:
        logging.error('Database file does not exist or is not writable')
        return False

def check_scraper_workers():
    try:
        subprocess.check_output(['pgrep', '-f', 'scraper_worker'])
        logging.info('Scraper workers are running')
        return True
    except subprocess.CalledProcessError:
        logging.error('Scraper workers are not running')
        return False

def main():
    logging.info('Starting health check')
    checks = [
        ('FastAPI server', check_fastapi_server),
        ('Database file', check_database_file),
        ('Scraper workers', check_scraper_workers)
    ]
    for name, check in checks:
        if check():
            print(f'{name}: OK')
        else:
            print(f'{name}: FAILED')
    logging.info('Health check completed')

if __name__ == '__main__':
    main()
