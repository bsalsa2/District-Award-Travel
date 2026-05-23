import os
import subprocess
import time
import requests

# Get current instance count
def get_instance_count():
    response = requests.get('http://localhost:8080/instance_count')
    return int(response.text)

# Scale up
def scale_up(instance_count):
    subprocess.run(['docker-compose', 'up', '-d', '--scale', 'web=' + str(instance_count + 1)])

# Scale down
def scale_down(instance_count):
    subprocess.run(['docker-compose', 'up', '-d', '--scale', 'web=' + str(instance_count - 1)])

# Main function
def main():
    while True:
        instance_count = get_instance_count()
        response = requests.get('http://localhost:8080/predictions')
        predictions = response.json()
        if predictions['usage'] > instance_count * 100:
            scale_up(instance_count)
        elif predictions['usage'] < instance_count * 50:
            scale_down(instance_count)
        time.sleep(60)

if __name__ == '__main__':
    main()
