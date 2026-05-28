from platform.src.intelligence.award_travel_recommender import AwardTravelRecommender
from platform.src.pipeline.data_loader import DataLoader

class Pipeline:
    def __init__(self, db_path):
        self.db_path = db_path
        self.data_loader = DataLoader(db_path)
        self.recommender = AwardTravelRecommender(None, None)

    def run(self):
        user_preferences = self.data_loader.load_user_preferences()
        travel_history = self.data_loader.load_travel_history()
        self.recommender.user_preferences = user_preferences
        self.recommender.travel_history = travel_history
        self.recommender.fit()

    def get_recommendations(self, user_id):
        return self.recommender.get_recommendations(user_id)

    def close(self):
        self.data_loader.close()
