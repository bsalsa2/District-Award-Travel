from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://awardtravel:awardtravel@db:5432/awardtravel"
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    points = db.Column(db.Integer, nullable=False)

class AwardTravel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user = db.relationship("User", backref=db.backref("award_travels", lazy=True))
    destination = db.Column(db.String(100), nullable=False)
    points_required = db.Column(db.Integer, nullable=False)

@app.route("/book", methods=["POST"])
def book_award_travel():
    user_id = request.json["user_id"]
    destination = request.json["destination"]
    user = User.query.get(user_id)
    if user.points >= AwardTravel.query.filter_by(destination=destination).first().points_required:
        award_travel = AwardTravel(user_id=user_id, destination=destination)
        db.session.add(award_travel)
        user.points -= AwardTravel.query.filter_by(destination=destination).first().points_required
        db.session.commit()
        return jsonify({"message": "Award travel booked successfully"})
    else:
        return jsonify({"message": "Insufficient points"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
