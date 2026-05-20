from flask import Flask, jsonify
import psycopg2

app = Flask(__name__)

@app.route("/metrics")
def metrics():
    conn = psycopg2.connect(
        host="db",
        database="metrics",
        user="user",
        password="password"
    )
    cur = conn.cursor()
    cur.execute("SELECT * FROM metrics")
    metrics = cur.fetchone()
    conn.close()
    return jsonify({
        "booking_requests": metrics[0],
        "award_redemptions": metrics[1],
        "customer_engagement": metrics[2]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
