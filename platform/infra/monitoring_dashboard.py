import os
import sys
import time
from datetime import datetime
import logging
import requests

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the monitoring dashboard URL
MONITORING_DASHBOARD_URL = 'http://localhost:8080'

# Define the alerting system URL
ALERTING_SYSTEM_URL = 'http://localhost:8081'

def get_monitoring_data():
    """
    Get the monitoring data from the monitoring dashboard.
    """
    try:
        response = requests.get(MONITORING_DASHBOARD_URL)
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f'Failed to get monitoring data: {response.status_code}')
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f'Failed to get monitoring data: {e}')
        return None

def send_alert(alert_data):
    """
    Send an alert to the alerting system.
    """
    try:
        response = requests.post(ALERTING_SYSTEM_URL, json=alert_data)
        if response.status_code == 200:
            logging.info(f'Alert sent successfully: {alert_data}')
        else:
            logging.error(f'Failed to send alert: {response.status_code}')
    except requests.exceptions.RequestException as e:
        logging.error(f'Failed to send alert: {e}')

def main():
    while True:
        monitoring_data = get_monitoring_data()
        if monitoring_data:
            # Check for issues in the monitoring data
            issues = []
            for metric in monitoring_data['metrics']:
                if metric['value'] > metric['threshold']:
                    issues.append({
                        'metric': metric['name'],
                        'value': metric['value'],
                        'threshold': metric['threshold']
                    })
            if issues:
                # Send an alert for each issue
                for issue in issues:
                    send_alert({
                        'metric': issue['metric'],
                        'value': issue['value'],
                        'threshold': issue['threshold']
                    })
        time.sleep(60)  # Check every 60 seconds

if __name__ == '__main__':
    main()
