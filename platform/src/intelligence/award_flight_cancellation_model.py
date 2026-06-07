import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

class AwardFlightCancellationModel:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100)

    def train(self, X, y):
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_test)
        print('Model accuracy:', accuracy_score(y_test, y_pred))

    def predict(self, X):
        return self.model.predict(X)

# Example usage:
# model = AwardFlightCancellationModel()
# X = np.array([[1, 2, 3], [4, 5, 6]])
# y = np.array([0, 1])
# model.train(X, y)
# print(model.predict(np.array([[7, 8, 9]])))
