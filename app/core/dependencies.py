"""
FastAPI dependencies
"""
import logging

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.core.security import verify_token
from app.models.database import User
from app.services.auth import AuthService
from app.services.clients import ClientService
from app.infrastructure.wireguard.backend import WireGuardBackend

security = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    if credentials is None:
        raise AuthenticationError("Authentication credentials were not provided")

    username = verify_token(credentials.credentials)
    if username is None:
        logger.warning("Token validation failed", extra={"event": "auth.invalid_token"})
        raise AuthenticationError("Could not validate credentials")

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise AuthenticationError("Could not validate credentials")

    return user


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """Build the auth service for request scope."""
    return AuthService(db)


def get_wireguard_backend() -> WireGuardBackend:
    """Build the WireGuard infrastructure adapter."""
    return WireGuardBackend()


def get_client_service(
    db: Session = Depends(get_db),
    backend: WireGuardBackend = Depends(get_wireguard_backend),
) -> ClientService:
    """Build the client service for request scope."""
    return ClientService(db=db, backend=backend)
