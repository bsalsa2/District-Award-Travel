from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import pandas as pd

class ExplainableAI:
    def __init__(self):
        self.model = RandomForestClassifier()
        self.data = pd.read_csv("award_data.csv")

    def get_recommendations(self, user):
        user_data = self.data[self.data["user_id"] == user["id"]]
        user_data = user_data.drop(["user_id"], axis=1)
        recommendations = self.model.predict(user_data)
        return [{"award_id": recommendation} for recommendation in recommendations]

    def explain_recommendation(self, user, award_id):
        user_data = self.data[self.data["user_id"] == user["id"]]
        user_data = user_data.drop(["user_id"], axis=1)
        explanation = self.model.feature_importances_
        return {"explanation": explanation}
