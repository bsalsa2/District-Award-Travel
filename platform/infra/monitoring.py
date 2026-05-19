import requests
import time

def monitor_system():
    while True:
        # Get system metrics
        response = requests.get('http://localhost:9090/api/v1/query', params={'query': 'cpu_usage_percent'})
        cpu_usage = response.json()['data']['result'][0]['value'][1]

        response = requests.get('http://localhost:9090/api/v1/query', params={'query': 'memory_usage_percent'})
        memory_usage = response.json()['data']['result'][0]['value'][1]

        # Print system metrics
        print(f'CPU usage: {cpu_usage}%')
        print(f'Memory usage: {memory_usage}%')

        time.sleep(10)

if __name__ == '__main__':
    monitor_system()
