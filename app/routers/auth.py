"""
Authentication routes
"""
from fastapi import APIRouter, Depends

from app.core.dependencies import get_auth_service, get_current_user
from app.core.exceptions import AuthenticationError, ConflictError
from app.models.database import User
from app.models.schemas import UserCreate, UserLogin, Token, MessageResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=MessageResponse)
async def register(
    user_data: UserCreate,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Register a new user - requires authentication"""
    if auth_service.get_user_by_username(user_data.username):
        raise ConflictError("Username already registered")

    auth_service.create_user(user_data)
    return MessageResponse(message="User created successfully")


@router.post("/login", response_model=Token)
async def login(
    user_data: UserLogin,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Authenticate user and return JWT token"""
    user = auth_service.authenticate_user(user_data.username, user_data.password)
    if not user:
        raise AuthenticationError("Incorrect username or password")

    return auth_service.create_access_token_for_user(user.username)
