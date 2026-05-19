import os
import time
import psutil
from flask import Flask, jsonify
import logging

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

cpu_usage_threshold = int(os.environ.get("CPU_USAGE_THRESHOLD", 80))
alert_history_size = int(os.environ.get("ALERT_HISTORY_SIZE", 100))

alert_history = []

def get_cpu_usage():
    return psutil.cpu_percent()

def check_cpu_usage():
    cpu_usage = get_cpu_usage()
    if cpu_usage > cpu_usage_threshold:
        logger.warning(f"CPU usage is high: {cpu_usage}%")
        alert_history.append({"timestamp": time.time(), "message": f"CPU usage is high: {cpu_usage}%"})
        if len(alert_history) > alert_history_size:
            alert_history.pop(0)

@app.route("/cpu-usage", methods=["GET"])
def get_cpu_usage_api():
    return jsonify({"cpu_usage": get_cpu_usage()})

@app.route("/alert-history", methods=["GET"])
def get_alert_history_api():
    return jsonify({"alert_history": alert_history})

if __name__ == "__main__":
    while True:
        check_cpu_usage()
        time.sleep(1)
    app.run(host="0.0.0.0", port=8081)
