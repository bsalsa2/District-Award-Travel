import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

class AwardTravelForecastingModel:
    def __init__(self):
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)

    def train(self, data):
        X = data.drop(['availability'], axis=1)
        y = data['availability']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        print(f'MSE: {mse}')

    def predict(self, data):
        return self.model.predict(data)

    def save(self, filename):
        import pickle
        with open(filename, 'wb') as f:
            pickle.dump(self.model, f)

    def load(self, filename):
        import pickle
        with open(filename, 'rb') as f:
            self.model = pickle.load(f)
