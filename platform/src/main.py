from fastapi import FastAPI, Request
from platform.src.pipeline.pipeline import Pipeline

app = FastAPI()

@app.post("/recommendations")
async def get_recommendations(request: Request):
    data = await request.json()
    user_id = data['userId']
    pipeline = Pipeline('database.db')
    pipeline.run()
    recommendations = pipeline.get_recommendations(user_id)
    pipeline.close()
    return {'recommendations': recommendations}
