from flask import Flask, request, jsonify
import numpy as np

app = Flask(__name__)

# Define anomaly detection function
def detect_anomalies(data):
    mean = np.mean(data)
    std = np.std(data)
    anomalies = [x for x in data if np.abs(x - mean) > 2 * std]
    return anomalies

@app.route('/detect', methods=['POST'])
def detect():
    data = request.get_json()
    anomalies = detect_anomalies(data)
    return jsonify({'anomalies': anomalies})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8001)
