from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

@app.route('/predict', methods=['POST'])
def predict():
    data = request.get_json()
    response = requests.post('http://ml-model:8000/predict', json=data)
    return jsonify(response.json())

@app.route('/detect', methods=['POST'])
def detect():
    data = request.get_json()
    response = requests.post('http://anomaly-detector:8001/detect', json=data)
    return jsonify(response.json())

@app.route('/respond', methods=['POST'])
def respond():
    data = request.get_json()
    response = requests.post('http://incident-responder:8002/respond', json=data)
    return jsonify(response.json())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
