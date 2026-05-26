import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from api import database as api_db
from api.routes import auth, scans, users
from config.settings import get_settings
from core.services.exceptions import NotFound, Forbidden, LimitExceeded, InvalidState

logger = logging.getLogger(__name__)


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


@app.exception_handler(NotFound)
async def not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(Forbidden)
async def forbidden_handler(request, exc):
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(LimitExceeded)
async def limit_exceeded_handler(request, exc):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidState)
async def invalid_state_handler(request, exc):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method, request.url.path, exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred"},
    )
