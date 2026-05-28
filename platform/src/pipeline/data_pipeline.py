import sqlite3
import json
from platform.src.intelligence.recommendation_system import RecommendationSystem

class DataPipeline:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.recommendation_system = RecommendationSystem(db_path)

    def load_data(self):
        self.cursor.execute('SELECT * FROM user_travel_history')
        data = self.cursor.fetchall()
        return data

    def preprocess_data(self, data):
        travel_history = []
        for row in data:
            user_id, destination, travel_date = row
            travel_history.append([user_id, destination, travel_date])
        return travel_history

    def fit_model(self, data):
        self.recommendation_system.fit_model(data)

    def predict(self, user_id):
        return self.recommendation_system.predict(user_id)

    def get_recommendations(self, user_id):
        return self.recommendation_system.get_recommendations(user_id)

# Example usage:
if __name__ == '__main__':
    db_path = 'platform/db/award_travel.db'
    data_pipeline = DataPipeline(db_path)
    data = data_pipeline.load_data()
    preprocessed_data = data_pipeline.preprocess_data(data)
    data_pipeline.fit_model(preprocessed_data)
    user_id = 1
    recommendations = data_pipeline.get_recommendations(user_id)
    print(recommendations)
