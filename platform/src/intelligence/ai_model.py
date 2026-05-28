import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

class AIModel:
    def __init__(self):
        self.model = RandomForestRegressor()

    def train(self, data):
        X = data.drop(["target"], axis=1)
        y = data["target"]
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)

    def generate_insights(self, data):
        predictions = self.model.predict(data)
        insights = []
        for i, prediction in enumerate(predictions):
            insights.append({"id": i, "prediction": prediction})
        return insights

ai_model = AIModel()
