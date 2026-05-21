from fastapi import FastAPI
from platform.src.intelligence.award_prediction_model import AwardPredictionModel
from platform.src.pipeline.pipeline import Pipeline

app = FastAPI()

@app.post("/predict")
async def predict(user: int, award: int, behavior: int):
    model = AwardPredictionModel(100, 100, 100)
    pipeline = Pipeline('data.csv')
    pipeline.run()
    prediction = model.predict([[user]], [[award]], [[behavior]])
    return {"prediction": prediction}
