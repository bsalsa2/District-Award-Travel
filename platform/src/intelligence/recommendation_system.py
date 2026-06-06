import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from platform.src.pipeline.data_loader import load_user_data, load_award_travel_data

class RecommendationSystem:
    def __init__(self):
        self.user_data = load_user_data()
        self.award_travel_data = load_award_travel_data()
        self.vectorizer = TfidfVectorizer()

    def train(self):
        user_preferences = [user['preferences'] for user in self.user_data]
        award_travel_descriptions = [award['description'] for award in self.award_travel_data]

        user_vectors = self.vectorizer.fit_transform(user_preferences)
        award_travel_vectors = self.vectorizer.transform(award_travel_descriptions)

        self.user_vectors = user_vectors
        self.award_travel_vectors = award_travel_vectors

    def recommend(self, user_id):
        user_vector = self.user_vectors[user_id]
        similarities = cosine_similarity(user_vector, self.award_travel_vectors)
        top_award_travels = np.argsort(-similarities[0])[:5]

        recommended_award_travels = []
        for index in top_award_travels:
            recommended_award_travels.append(self.award_travel_data[index])

        return recommended_award_travels

    def update_user_preferences(self, user_id, new_preferences):
        self.user_data[user_id]['preferences'] = new_preferences
        self.train()

    def update_award_travel_data(self, new_award_travel_data):
        self.award_travel_data = new_award_travel_data
        self.train()

# Example usage:
recommendation_system = RecommendationSystem()
recommendation_system.train()
recommended_award_travels = recommendation_system.recommend(0)
print(recommended_award_travels)
