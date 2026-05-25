import numpy as np
from sklearn.linear_model import LinearRegression

class ValuationModel:
    def __init__(self):
        self.model = LinearRegression()

    def train(self, X: np.ndarray, y: np.ndarray):
        self.model.fit(X, y)

    def predict(self, X: np.ndarray):
        return self.model.predict(X)
