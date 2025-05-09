from fastapi import FastAPI
from app.api import router

app = FastAPI(title="ATS Resume Ranking API")
app.include_router(router)
