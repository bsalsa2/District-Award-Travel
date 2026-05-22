from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/search', methods=['GET'])
def search():
    # Implement award search logic here
    return jsonify({'results': []})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
