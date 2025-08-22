from fastapi import FastAPI
from server.config.db import test_connection
from server.api import report_apis
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Store Monitoring API",
    description="API for generating uptime/downtime reports for stores",
    version="1.0.0",
)

test_connection()

app.include_router(report_apis.router, prefix="/api")
app.mount("/reports", StaticFiles(directory="reports"), name="reports")


@app.get("/")
async def root():
    return {"message": "Welcome to Store Monitoring API"}
