from flask import Flask, request, jsonify
import psycopg2

app = Flask(__name__)

# Database connection settings
DATABASE_URL = 'postgres://user:password@db:5432/award-travel'

# Create a connection to the database
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# Define a route for the award travel service
@app.route('/award-travel', methods=['GET'])
def award_travel():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM award_travels')
    award_travels = cur.fetchall()
    conn.close()
    return jsonify(award_travels)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
