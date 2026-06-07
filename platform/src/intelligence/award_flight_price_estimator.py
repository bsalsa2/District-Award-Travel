import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

class AwardFlightPriceEstimator:
    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)

    def train(self, X, y):
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        print(f"Model trained with MSE: {mse}")

    def predict(self, X):
        return self.model.predict(X)

    def save(self, path):
        import pickle
        with open(path, 'wb') as f:
            pickle.dump(self.model, f)

    def load(self, path):
        import pickle
        with open(path, 'rb') as f:
            self.model = pickle.load(f)
