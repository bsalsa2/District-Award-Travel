from fastapi import FastAPI
from platform.src.services.redemption_tracker import app as redemption_app

app = FastAPI()

app.mount("/api", redemption_app)
