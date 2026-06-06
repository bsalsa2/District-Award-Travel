import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import sqlite3
import pandas as pd

class AwardFlightRecommender:
    def __init__(self):
        self.conn = sqlite3.connect('/home/runner/work/District-Award-Travel/District-Award-Travel/platform/db/award_flights.db')
        self.cursor = self.conn.cursor()

    def load_data(self):
        query = "SELECT * FROM award_flights"
        self.cursor.execute(query)
        rows = self.cursor.fetchall()
        data = pd.DataFrame(rows)
        return data

    def train_model(self):
        data = self.load_data()
        X = data.drop(['recommended'], axis=1)
        y = data['recommended']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        model = RandomForestClassifier(n_estimators=100)
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        print(f"Model accuracy: {accuracy:.3f}")
        return model

    def recommend_flights(self, user_input):
        model = self.train_model()
        user_data = pd.DataFrame([user_input])
        prediction = model.predict(user_data)
        return prediction[0]

    def close_connection(self):
        self.conn.close()
