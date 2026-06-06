import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

class BookingModel:
    def __init__(self):
        self.model = RandomForestRegressor()

    def train(self, X, y):
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)

    def predict(self, X):
        return self.model.predict(X)

# Example usage
X = np.array([[1, 2, 3], [4, 5, 6]])
y = np.array([10, 20])
model = BookingModel()
model.train(X, y)
print(model.predict(X))
