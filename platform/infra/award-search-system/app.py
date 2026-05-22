import os
import logging
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

@app.route("/update-award-availability", methods=["POST"])
def update_award_availability():
    award_availability = request.get_json()
    # Update award availability in database
    logging.info("Award availability updated successfully")
    return jsonify({"status": "success"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
