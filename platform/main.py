from fastapi import FastAPI
from platform.src.api.award_availability import app as award_app

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Welcome to District Award Travel"}

app.mount("/award", award_app)
