from fastapi import FastAPI
from platform.src.endpoints import client_redemption_history

app = FastAPI()

# Include the client redemption history endpoint
app.include_router(client_redemption_history.router)
