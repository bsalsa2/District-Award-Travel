from fastapi import FastAPI
from platform.src.pipeline.data_pipeline import DataPipeline
from platform.src.intelligence.multimodal_ai_model import MultimodalAIModel

app = FastAPI()

@app.post("/predict")
async def predict(user_data: dict):
    pipeline = DataPipeline('database.db')
    prediction = pipeline.predict(user_data['name'])
    return {"prediction": prediction}
