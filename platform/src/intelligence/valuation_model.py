import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

class ValuationModel:
    def __init__(self):
        self.model = RandomForestRegressor()

    def train(self, data: List[Dict]):
        # Extract the features and target variable
        X = np.array([[item['miles'], item['price']] for item in data])
        y = np.array([item['value'] for item in data])

        # Split the data into training and testing sets
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Train the model
        self.model.fit(X_train, y_train)

    def predict(self, data: List[Dict]):
        # Extract the features
        X = np.array([[item['miles'], item['price']] for item in data])

        # Make predictions
        predictions = self.model.predict(X)

        return predictions
