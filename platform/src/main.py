from fastapi import FastAPI
from fastapi.responses import JSONResponse
import json
import redis

app = FastAPI()

redis_client = redis.Redis(host='localhost', port=6379, db=0)

@app.get("/api/transfer_bonuses")
async def get_transfer_bonuses():
    bonuses = redis_client.get('transfer_bonuses')
    if bonuses:
        return JSONResponse(content=json.loads(bonuses), media_type="application/json")
    else:
        return JSONResponse(content=[], media_type="application/json")
