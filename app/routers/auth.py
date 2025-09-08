"""
Authentication routes
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.database import User
from app.models.schemas import UserCreate, UserLogin, Token, MessageResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=MessageResponse)
async def register(
    user_data: UserCreate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Register a new user - requires authentication"""
    if AuthService.get_user_by_username(db, user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    AuthService.create_user(db, user_data)
    return MessageResponse(message="User created successfully")


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return JWT token"""
    user = AuthService.authenticate_user(
        db, user_data.username, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthService.create_access_token_for_user(user.username)
