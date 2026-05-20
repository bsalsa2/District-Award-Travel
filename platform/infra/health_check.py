import requests
import logging

def check_dashboard_health():
    try:
        response = requests.get('http://localhost:8080')
        if response.status_code == 200:
            logging.getLogger('district-award-travel').info('Monitoring dashboard is healthy')
            return True
        else:
            logging.getLogger('district-award-travel').error('Monitoring dashboard is not healthy')
            return False
    except requests.exceptions.RequestException as e:
        logging.getLogger('district-award-travel').error('Error checking monitoring dashboard health: %s', e)
        return False
