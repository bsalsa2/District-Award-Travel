from flask import Flask, render_template, request
import requests

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/bookings")
def bookings():
    response = requests.get("http://award-travel-logic:8081/bookings")
    return response.json()

@app.route("/customers")
def customers():
    response = requests.get("http://award-travel-logic:8081/customers")
    return response.json()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
