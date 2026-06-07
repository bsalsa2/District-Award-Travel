import requests
import json
import time

# Define the travel API endpoint
TRAVEL_API_ENDPOINT = "https://api.travel.com/award-flights"

# Define the Grafana dashboard API endpoint
GRAFANA_API_ENDPOINT = "http://grafana:3000/api"

# Define the Grafana dashboard ID
DASHBOARD_ID = "award-flight-dashboard"

# Define the metrics to collect
METRICS = [
    "award_flight_availability",
    "booking_trends",
    "client_redemption_rates"
]

def collect_metrics():
    metrics_data = {}
    for metric in METRICS:
        response = requests.get(f"{TRAVEL_API_ENDPOINT}/{metric}")
        if response.status_code == 200:
            metrics_data[metric] = response.json()
        else:
            metrics_data[metric] = None
    return metrics_data

def update_grafana_dashboard(metrics_data):
    # Create a new dashboard if it doesn't exist
    response = requests.get(f"{GRAFANA_API_ENDPOINT}/dashboards/{DASHBOARD_ID}")
    if response.status_code != 200:
        create_dashboard()
    
    # Update the dashboard panels
    for metric, data in metrics_data.items():
        if data:
            update_panel(metric, data)

def create_dashboard():
    dashboard_data = {
        "title": "Award Flight Dashboard",
        "rows": [
            {
                "title": "Award Flight Availability",
                "panels": [
                    {
                        "id": 1,
                        "title": "Award Flight Availability",
                        "type": "graph",
                        "span": 12,
                        "query": "award_flight_availability"
                    }
                ]
            },
            {
                "title": "Booking Trends",
                "panels": [
                    {
                        "id": 2,
                        "title": "Booking Trends",
                        "type": "graph",
                        "span": 12,
                        "query": "booking_trends"
                    }
                ]
            },
            {
                "title": "Client Redemption Rates",
                "panels": [
                    {
                        "id": 3,
                        "title": "Client Redemption Rates",
                        "type": "graph",
                        "span": 12,
                        "query": "client_redemption_rates"
                    }
                ]
            }
        ]
    }
    response = requests.post(f"{GRAFANA_API_ENDPOINT}/dashboards", json=dashboard_data)
    if response.status_code != 200:
        print("Failed to create dashboard")

def update_panel(metric, data):
    panel_data = {
        "id": 1,
        "title": metric,
        "type": "graph",
        "span": 12,
        "query": metric
    }
    response = requests.put(f"{GRAFANA_API_ENDPOINT}/dashboards/{DASHBOARD_ID}/panels/{panel_data['id']}", json=panel_data)
    if response.status_code != 200:
        print("Failed to update panel")

def main():
    while True:
        metrics_data = collect_metrics()
        update_grafana_dashboard(metrics_data)
        time.sleep(60)

if __name__ == "__main__":
    main()
