from contextlib import asynccontextmanager
from fastapi import FastAPI
from api import database as api_db
from api.routes import auth, scans, users
from config.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if not settings.api_secret_key:
        raise RuntimeError("API_SECRET_KEY must be set before starting the API server")
    api_db.init()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(scans.router, prefix="/api/v1/scans", tags=["scans"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
