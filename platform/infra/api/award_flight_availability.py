from flask import Flask, request, jsonify
from platform.infra.monitoring.award_space_alerts import process_award_space_update

app = Flask(__name__)

@app.route('/award-space-update', methods=['POST'])
def award_space_update():
    data = request.get_json()
    process_award_space_update(data)
    return jsonify({'message': 'Award space update processed'}), 200

if __name__ == '__main__':
    app.run(debug=True)
