from flask import Flask, jsonify
import psycopg2

app = Flask(__name__)

@app.route("/bookings")
def bookings():
    conn = psycopg2.connect(
        host="db",
        database="award_travel",
        user="user",
        password="password"
    )
    cur = conn.cursor()
    cur.execute("SELECT * FROM bookings")
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.route("/customers")
def customers():
    conn = psycopg2.connect(
        host="db",
        database="award_travel",
        user="user",
        password="password"
    )
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers")
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
