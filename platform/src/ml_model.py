import asyncio
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from platform.src.data_pipeline import DataPipeline

class MLModel:
    def __init__(self):
        self.data_pipeline = DataPipeline()
        self.model = RandomForestRegressor()

    async def predict_award_travel_trends(self):
        data = await self.data_pipeline.get_award_availability()
        X = [item["award_id"] for item in data]
        y = [item["availability"] for item in data]
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)
        predictions = self.model.predict(X_test)
        return predictions.tolist()
