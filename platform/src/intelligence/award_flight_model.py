import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

class AwardFlightModel:
    def __init__(self):
        self.model = RandomForestRegressor()

    def train(self, X: np.ndarray, y: np.ndarray):
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_test)
        print(f'MSE: {mean_squared_error(y_test, y_pred)}')

    def predict(self, X: np.ndarray):
        return self.model.predict(X)
