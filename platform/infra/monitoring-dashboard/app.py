import os
import time
from flask import Flask, render_template, request
import requests

app = Flask(__name__)

@app.route("/")
def index():
    cpu_usage = requests.get("http://alerting-system:8081/cpu-usage").json()["cpu_usage"]
    alert_history = requests.get("http://alerting-system:8081/alert-history").json()["alert_history"]
    return render_template("index.html", cpu_usage=cpu_usage, alert_history=alert_history)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
