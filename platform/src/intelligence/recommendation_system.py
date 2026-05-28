import numpy as np
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
import sqlite3
import json

class RecommendationSystem:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.scaler = StandardScaler()
        self.nbrs = NearestNeighbors(n_neighbors=5, algorithm='brute', metric='euclidean')

    def load_data(self):
        self.cursor.execute('SELECT * FROM user_travel_history')
        data = self.cursor.fetchall()
        return data

    def preprocess_data(self, data):
        travel_history = []
        for row in data:
            user_id, destination, travel_date = row
            travel_history.append([user_id, destination, travel_date])
        return np.array(travel_history)

    def fit_model(self, data):
        scaled_data = self.scaler.fit_transform(data[:, 1:])
        self.nbrs.fit(scaled_data)

    def predict(self, user_id):
        self.cursor.execute('SELECT * FROM user_travel_history WHERE user_id = ?', (user_id,))
        user_data = self.cursor.fetchone()
        if user_data:
            user_destination = user_data[1]
            self.cursor.execute('SELECT * FROM destinations WHERE name = ?', (user_destination,))
            destination_data = self.cursor.fetchone()
            if destination_data:
                destination_id = destination_data[0]
                self.cursor.execute('SELECT * FROM award_travel_options WHERE destination_id = ?', (destination_id,))
                award_travel_options = self.cursor.fetchall()
                return award_travel_options
        return []

    def get_recommendations(self, user_id):
        award_travel_options = self.predict(user_id)
        if award_travel_options:
            return award_travel_options
        else:
            self.cursor.execute('SELECT * FROM award_travel_options')
            all_award_travel_options = self.cursor.fetchall()
            return all_award_travel_options

# Example usage:
if __name__ == '__main__':
    db_path = 'platform/db/award_travel.db'
    recommendation_system = RecommendationSystem(db_path)
    data = recommendation_system.load_data()
    preprocessed_data = recommendation_system.preprocess_data(data)
    recommendation_system.fit_model(preprocessed_data)
    user_id = 1
    recommendations = recommendation_system.get_recommendations(user_id)
    print(recommendations)
