import sqlite3
import pandas as pd
from platform.src.intelligence.award_flight_recommender import AwardFlightRecommender

class AwardFlightPipeline:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.recommender = AwardFlightRecommender(db_path)

    def load_data(self):
        # Load data from database
        self.cursor.execute("SELECT * FROM user_search_history")
        search_history = self.cursor.fetchall()
        self.cursor.execute("SELECT * FROM user_travel_preferences")
        travel_preferences = self.cursor.fetchall()
        self.cursor.execute("SELECT * FROM loyalty_program_affiliations")
        loyalty_program_affiliations = self.cursor.fetchall()

        # Merge data into a single dataframe
        search_history_df = pd.DataFrame(search_history)
        travel_preferences_df = pd.DataFrame(travel_preferences)
        loyalty_program_affiliations_df = pd.DataFrame(loyalty_program_affiliations)
        df = pd.merge(search_history_df, travel_preferences_df, on='user_id')
        df = pd.merge(df, loyalty_program_affiliations_df, on='user_id')

        return df

    def train_model(self):
        # Train award flight recommender model
        self.recommender.train_model()

    def recommend_flights(self, user_id):
        # Recommend flights using trained model
        return self.recommender.recommend_flights(user_id)

    def close_connection(self):
        self.conn.close()
