import sqlite3
import pandas as pd
from platform.src.intelligence.multimodal_ai_model import MultimodalAIModel

class DataPipeline:
    def __init__(self, db_name):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()

    def fetch_user_data(self):
        query = "SELECT * FROM user_data"
        self.cursor.execute(query)
        rows = self.cursor.fetchall()
        return rows

    def fetch_travel_history(self):
        query = "SELECT * FROM travel_history"
        self.cursor.execute(query)
        rows = self.cursor.fetchall()
        return rows

    def train_model(self):
        user_data = self.fetch_user_data()
        travel_history = self.fetch_travel_history()
        X = pd.DataFrame(user_data)
        y = pd.DataFrame(travel_history)
        model = MultimodalAIModel()
        accuracy = model.train(X, y)
        return accuracy

    def predict(self, user_id):
        query = "SELECT * FROM user_data WHERE user_id = ?"
        self.cursor.execute(query, (user_id,))
        row = self.cursor.fetchone()
        X = pd.DataFrame([row])
        model = MultimodalAIModel()
        prediction = model.predict(X)
        return prediction
