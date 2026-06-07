import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score

class Estimator:
    def __init__(self):
        self.model = RandomForestRegressor()

    def train(self, X, y):
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, np.round(y_pred))
        precision = precision_score(y_test, np.round(y_pred))
        recall = recall_score(y_test, np.round(y_pred))
        return accuracy, precision, recall

    def predict(self, X):
        return self.model.predict(X)
