from flask import Flask, jsonify
import requests
from prometheus_client import Counter, Gauge, start_http_server

app = Flask(__name__)

# Prometheus metrics
award_flight_counter = Counter('award_flight_count', 'Number of award flights')
award_flight_gauge = Gauge('award_flight_availability', 'Award flight availability')

# Award flight monitoring endpoint
@app.route('/monitor', methods=['GET'])
def monitor():
    award_flights = requests.get('https://example.com/award-flights').json()
    award_flight_counter.inc(len(award_flights))
    award_flight_gauge.set(len(award_flights))
    return jsonify({'award_flights': award_flights})

# Health check endpoint
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    start_http_server(8080)
    app.run(port=8080)
