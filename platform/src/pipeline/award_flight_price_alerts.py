import sqlite3
from platform.src.intelligence.award_flight_price_estimator import AwardFlightPriceEstimator
import numpy as np

class AwardFlightPriceAlerts:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.estimator = AwardFlightPriceEstimator()

    def get_flight_data(self):
        self.cursor.execute("SELECT * FROM flights")
        return self.cursor.fetchall()

    def train_estimator(self):
        flights = self.get_flight_data()
        X = np.array([flight[1:] for flight in flights])
        y = np.array([flight[0] for flight in flights])
        self.estimator.train(X, y)

    def predict_flight_prices(self):
        flights = self.get_flight_data()
        X = np.array([flight[1:] for flight in flights])
        predicted_prices = self.estimator.predict(X)
        return predicted_prices

    def send_price_alerts(self):
        predicted_prices = self.predict_flight_prices()
        self.cursor.execute("SELECT * FROM clients")
        clients = self.cursor.fetchall()
        for client in clients:
            client_id, client_email = client
            self.cursor.execute("SELECT * FROM client_flights WHERE client_id = ?", (client_id,))
            client_flights = self.cursor.fetchall()
            for flight in client_flights:
                flight_id, flight_price = flight
                predicted_price = predicted_prices[flight_id]
                if predicted_price < flight_price:
                    # Send email to client
                    print(f"Sending price alert to client {client_id} for flight {flight_id}")

    def close(self):
        self.conn.close()
