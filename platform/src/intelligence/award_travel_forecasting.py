import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

class AwardTravelForecasting:
    def __init__(self, data):
        self.data = data
        self.model = RandomForestRegressor()

    def train(self):
        X = self.data.drop(['availability'], axis=1)
        y = self.data['availability']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_test)
        print(f'MSE: {mean_squared_error(y_test, y_pred)}')

    def predict(self, input_data):
        return self.model.predict(input_data)

# Example usage:
# data = pd.read_csv('award_travel_data.csv')
# forecasting = AwardTravelForecasting(data)
# forecasting.train()
# input_data = pd.DataFrame({'date': ['2024-01-01'], 'destination': ['New York']})
# print(forecasting.predict(input_data))
