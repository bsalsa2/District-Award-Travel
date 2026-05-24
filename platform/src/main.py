from fastapi import FastAPI
from platform.src.pipeline.user_pipeline import UserPipeline
from platform.src.models.user import User

app = FastAPI()

@app.post("/users")
async def create_user(user: User):
    pipeline = UserPipeline('district_award_travel.db')
    pipeline.create_user(user)
    return {"message": "User created successfully"}

@app.get("/users")
async def get_users():
    pipeline = UserPipeline('district_award_travel.db')
    users = []
    # Add logic to retrieve users from database
    return users
