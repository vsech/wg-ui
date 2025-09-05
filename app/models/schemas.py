"""
Pydantic schemas for request/response models
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# User schemas
class UserBase(BaseModel):
    """Base user schema"""
    username: str


class UserCreate(UserBase):
    """User creation schema"""
    password: str


class UserLogin(UserBase):
    """User login schema"""
    password: str


class UserResponse(UserBase):
    """User response schema"""
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Authentication schemas
class Token(BaseModel):
    """JWT token response schema"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token data schema"""
    username: Optional[str] = None


# Client schemas
class ClientBase(BaseModel):
    """Base client schema"""
    name: str


class ClientCreate(ClientBase):
    """Client creation schema"""
    dns: Optional[str] = "8.8.8.8, 8.8.4.4"


class ClientResponse(ClientBase):
    """Client response schema"""
    id: int
    ip_address: str
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class ClientConfig(ClientBase):
    """Client configuration schema with QR code"""
    config: str
    qr_code: str


class QRCodeResponse(BaseModel):
    """QR code response schema"""
    qr_code: str


class MessageResponse(BaseModel):
    """Generic message response schema"""
    message: str
