#!/usr/bin/env python3
"""
FastAPI backend for WireGuard Client Manager
Provides REST API endpoints for managing WireGuard clients with JWT authentication
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.routers import auth, clients
from app.services.auth import AuthService
from app.core.database import SessionLocal
from app.models.schemas import UserCreate

# FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(clients.router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()

    # Create default admin user if no users exist
    db = SessionLocal()
    try:
        if not AuthService.get_user_by_username(db, "admin"):
            admin_user_data = UserCreate(username="admin", password="admin123")
            AuthService.create_user(db, admin_user_data)
            print("Default admin user created: admin/admin123")
    finally:
        db.close()


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "message": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "endpoints": {
            "auth": "/auth/login, /auth/register",
            "clients": "/clients (GET, POST)",
            "client_operations": "/clients/{name} (DELETE), /clients/{name}/qr (GET)"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
