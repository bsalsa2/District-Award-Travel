import numpy as np
from sklearn.linear_model import LinearRegression

class AwardTravelModel:
    def __init__(self):
        self.model = LinearRegression()

    def train(self, X, y):
        self.model.fit(X, y)

    def predict(self, X):
        return self.model.predict(X)

# Example usage:
# award_travel_model = AwardTravelModel()
# X = np.array([[1, 2], [3, 4]])
# y = np.array([5, 6])
# award_travel_model.train(X, y)
# print(award_travel_model.predict(np.array([[7, 8]])))
