import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import sqlite3
import pandas as pd

class AwardFlightValueEstimator:
    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)

    def train(self, data):
        X = data[['origin_airport', 'destination_airport', 'airline', 'cabin_class', 'travel_date']]
        y = data['award_flight_value']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_test)
        print(f'MSE: {mean_squared_error(y_test, y_pred)}')

    def predict(self, data):
        return self.model.predict(data)

    def save(self):
        import pickle
        with open('award_flight_value_estimator.pkl', 'wb') as f:
            pickle.dump(self.model, f)

    def load(self):
        import pickle
        with open('award_flight_value_estimator.pkl', 'rb') as f:
            self.model = pickle.load(f)

def get_historical_data():
    conn = sqlite3.connect('award_flights.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM award_flights')
    data = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    df = pd.DataFrame(data, columns=columns)
    return df

def main():
    estimator = AwardFlightValueEstimator()
    data = get_historical_data()
    estimator.train(data)
    estimator.save()

if __name__ == '__main__':
    main()
