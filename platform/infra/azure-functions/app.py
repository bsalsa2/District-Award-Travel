import logging
import os

from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/hello', methods=['GET'])
def hello():
    logging.info('Received request')
    return jsonify({'message': 'Hello from Azure Functions!'})

if __name__ == '__main__':
    app.run(debug=True)
