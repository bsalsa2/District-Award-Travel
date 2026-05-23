from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "postgres://user:password@postgres:5432/database"
db = SQLAlchemy(app)

class AwardTravelService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=False)

@app.route("/award-travel-services", methods=["GET"])
def get_award_travel_services():
    services = AwardTravelService.query.all()
    return jsonify([{"id": service.id, "name": service.name, "description": service.description} for service in services])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
