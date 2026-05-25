import numpy as np
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics.pairwise import cosine_similarity

class RecommendationEngine:
    def __init__(self, user_profiles, award_flights):
        self.user_profiles = user_profiles
        self.award_flights = award_flights
        self.nbrs = NearestNeighbors(n_neighbors=5, algorithm='brute', metric='cosine')

    def fit(self):
        self.nbrs.fit(self.user_profiles)

    def recommend(self, user_id):
        distances, indices = self.nbrs.kneighbors([self.user_profiles[user_id]])
        return [self.award_flights[i] for i in indices[0]]

def get_user_profiles(db: sqlite3.Connection):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM user_profiles")
    return np.array(cursor.fetchall())

def get_award_flights(db: sqlite3.Connection):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM award_flights")
    return np.array(cursor.fetchall())

def create_recommendation_engine(db: sqlite3.Connection):
    user_profiles = get_user_profiles(db)
    award_flights = get_award_flights(db)
    return RecommendationEngine(user_profiles, award_flights)
