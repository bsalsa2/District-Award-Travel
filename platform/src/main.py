from fastapi import FastAPI
from pydantic import BaseModel
from award_travel_model import AwardTravelModel
from data_pipeline import DataPipeline

app = FastAPI()

class SearchQuery(BaseModel):
    search_query: str

@app.post("/search")
async def search(search_query: SearchQuery):
    # Load data pipeline
    pipeline = DataPipeline('data.csv')
    scaled_train_data, scaled_test_data = pipeline.run_pipeline()

    # Load award travel model
    model = AwardTravelModel()

    # Make predictions
    predictions = model.predict(scaled_test_data)

    # Return results
    results = []
    for prediction in predictions:
        results.append({
            'title': prediction[0],
            'description': prediction[1]
        })
    return results
