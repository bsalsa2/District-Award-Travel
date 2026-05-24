import requests
import time

# Define a function to check the health of a service
def check_health(service_url):
    try:
        response = requests.get(service_url)
        if response.status_code == 200:
            return True
        else:
            return False
    except requests.exceptions.RequestException:
        return False

# Define a function to failover to a different service
def failover(service_url, backup_service_url):
    if not check_health(service_url):
        return backup_service_url
    else:
        return service_url

# Define a function to continuously check the health of a service and failover if necessary
def continuous_failover(service_url, backup_service_url):
    while True:
        service_url = failover(service_url, backup_service_url)
        time.sleep(60)
