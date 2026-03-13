#!/usr/bin/env python3
"""
FastAPI backend for WireGuard Client Manager.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import AppError, ConfigurationError
from app.core.logging import configure_logging
from app.models.schemas import UserCreate
from app.routers import auth, clients
from app.services.auth import AuthService

configure_logging()
logger = logging.getLogger(__name__)


def bootstrap_admin_user() -> None:
    """Create a bootstrap admin account when explicitly configured."""
    if not settings.bootstrap_admin_enabled:
        return

    db = SessionLocal()
    try:
        auth_service = AuthService(db)
        if auth_service.get_user_by_username(settings.bootstrap_admin_username):
            return

        auth_service.create_user(
            UserCreate(
                username=settings.bootstrap_admin_username,
                password=settings.bootstrap_admin_password.get_secret_value(),
            )
        )
        logger.info(
            "Bootstrap admin user created",
            extra={"event": "auth.bootstrap_admin_created"},
        )
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application startup/shutdown lifecycle."""
    if settings.secret_key is None:
        raise ConfigurationError("SECRET_KEY must be set before starting the API")
    logger.info("Application startup", extra={"event": "app.startup"})
    bootstrap_admin_user()
    yield
    logger.info("Application shutdown", extra={"event": "app.shutdown"})


app = FastAPI(
    title=settings.project_name,
    description=settings.project_description,
    version=settings.project_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(clients.router, prefix=settings.api_prefix)


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    """Render typed application errors consistently."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "code": exc.code,
            "details": exc.details,
        },
    )


@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "message": settings.project_name,
        "version": settings.project_version,
        "endpoints": {
            "auth": f"{settings.api_prefix}/auth/login, {settings.api_prefix}/auth/register",
            "clients": f"{settings.api_prefix}/clients (GET, POST)",
            "client_operations": (
                f"{settings.api_prefix}/clients/{{name}} (DELETE), "
                f"{settings.api_prefix}/clients/{{name}}/qr (GET)"
            ),
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
