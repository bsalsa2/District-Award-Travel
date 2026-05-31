import asyncio
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from platform.src.config import settings
from platform.src.data_pipeline import DataPipeline

app = FastAPI()

@app.get("/healthcheck")
async def healthcheck():
    return JSONResponse(content={"status": "ok"}, status_code=200)

@app.get("/ingest_data")
async def ingest_data():
    data_pipeline = DataPipeline()
    await data_pipeline.ingest_data()
    return JSONResponse(content={"status": "data ingested"}, status_code=200)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
