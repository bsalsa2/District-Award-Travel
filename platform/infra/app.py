from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://postgres:postgres@db:5432/award_travel"
db = SQLAlchemy(app)

class AwardTravel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=False)

@app.route("/awards", methods=["GET"])
def get_awards():
    awards = AwardTravel.query.all()
    return jsonify([{"id": award.id, "name": award.name, "description": award.description} for award in awards])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
