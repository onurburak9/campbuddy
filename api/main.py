from contextlib import asynccontextmanager
from fastapi import FastAPI
from api import database as api_db
from api.routes import auth, scans, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    api_db.init()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(scans.router, prefix="/api/v1/scans", tags=["scans"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
