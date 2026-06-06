import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

class TravelBookingModel:
    def __init__(self):
        self.model = RandomForestClassifier()
        self.train_data = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        self.test_data = np.array([[10, 11, 12], [13, 14, 15], [16, 17, 18]])
        self.labels = np.array([0, 1, 1])

    def train_model(self):
        X_train, X_test, y_train, y_test = train_test_split(self.train_data, self.labels, test_size=0.2)
        self.model.fit(X_train, y_train)
        return self.model.score(X_test, y_test)

    def get_travel_options(self):
        options = [
            {"origin": "New York", "destination": "Los Angeles", "travel_date": "2026-06-10"},
            {"origin": "Chicago", "destination": "New York", "travel_date": "2026-06-15"},
            {"origin": "Los Angeles", "destination": "Chicago", "travel_date": "2026-06-20"}
        ]
        return options
