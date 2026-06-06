import numpy as np
from sklearn.linear_model import LinearRegression

class FlightPriceModel:
    def __init__(self):
        self.model = LinearRegression()
        self.prices = {}

    def init_price(self, flight_number: str, departure_airport: str, arrival_airport: str):
        self.prices[(flight_number, departure_airport, arrival_airport)] = []

    def update_price(self, flight_number: str, departure_airport: str, arrival_airport: str, price: float):
        self.prices[(flight_number, departure_airport, arrival_airport)].append(price)
        # Train the model
        X = np.arange(len(self.prices[(flight_number, departure_airport, arrival_airport)])).reshape(-1, 1)
        y = np.array(self.prices[(flight_number, departure_airport, arrival_airport)])
        self.model.fit(X, y)

    def predict_price(self, flight_number: str, departure_airport: str, arrival_airport: str):
        if (flight_number, departure_airport, arrival_airport) in self.prices:
            # Predict the next price
            X = np.array([[len(self.prices[(flight_number, departure_airport, arrival_airport)])]])
            return self.model.predict(X)[0]
        else:
            return None
