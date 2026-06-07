from fastapi import FastAPI
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from platform.src.endpoints.award_flights import router

app = FastAPI()

app.include_router(router)

@app.get("/docs", include_in_schema=False)
async def get_docs():
    return get_redoc_html(openapi_url="/openapi.json", title="Award Flight API")

@app.get("/swagger", include_in_schema=False)
async def get_swagger():
    return get_swagger_ui_html(openapi_url="/openapi.json", title="Award Flight API")
