from flask import Flask, render_template, request
import requests

app = Flask(__name__)

@app.route("/")
def index():
    metrics_url = "http://metrics:8081/metrics"
    response = requests.get(metrics_url)
    metrics = response.json()
    return render_template("index.html", metrics=metrics)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
