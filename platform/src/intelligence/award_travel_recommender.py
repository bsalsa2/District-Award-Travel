import numpy as np
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

class AwardTravelRecommender:
    def __init__(self, user_preferences, travel_history):
        self.user_preferences = user_preferences
        self.travel_history = travel_history
        self.scaler = StandardScaler()
        self.nn_model = NearestNeighbors(n_neighbors=5, algorithm='brute', metric='cosine')

    def fit(self):
        scaled_preferences = self.scaler.fit_transform(self.user_preferences)
        self.nn_model.fit(scaled_preferences)

    def predict(self, user_id):
        user_preferences = self.user_preferences[user_id]
        scaled_preferences = self.scaler.transform([user_preferences])
        distances, indices = self.nn_model.kneighbors(scaled_preferences)
        return indices[0]

    def get_recommendations(self, user_id):
        recommended_travel_ids = self.predict(user_id)
        return [self.travel_history[id] for id in recommended_travel_ids]
