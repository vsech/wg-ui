"""
Client management routes
"""
from typing import List
from fastapi import APIRouter, Depends

from app.core.dependencies import get_client_service, get_current_user
from app.models.database import User
from app.models.schemas import ClientCreate, ClientResponse, ClientConfig, QRCodeResponse, MessageResponse
from app.services.clients import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("/", response_model=List[ClientResponse])
async def get_clients(
    current_user: User = Depends(get_current_user),
    client_service: ClientService = Depends(get_client_service),
):
    """Get list of all WireGuard clients"""
    return client_service.get_all_clients()


@router.post("/", response_model=ClientConfig)
async def create_client(
    client_data: ClientCreate,
    current_user: User = Depends(get_current_user),
    client_service: ClientService = Depends(get_client_service),
):
    """Create a new WireGuard client"""
    return client_service.create_client(client_data)


@router.delete("/{client_name}", response_model=MessageResponse)
async def delete_client(
    client_name: str,
    current_user: User = Depends(get_current_user),
    client_service: ClientService = Depends(get_client_service),
):
    """Delete a WireGuard client"""
    client_service.delete_client(client_name)
    return MessageResponse(message=f"Client {client_name} deleted successfully")


@router.get("/{client_name}/config", response_model=ClientConfig)
async def get_client_config(
    client_name: str,
    current_user: User = Depends(get_current_user),
    client_service: ClientService = Depends(get_client_service),
):
    """Get complete client configuration including config text, QR code and statistics"""
    return client_service.get_client_config(client_name)


@router.get("/{client_name}/qr", response_model=QRCodeResponse)
async def get_client_qr(
    client_name: str,
    current_user: User = Depends(get_current_user),
    client_service: ClientService = Depends(get_client_service),
):
    """Generate QR code for existing client configuration"""
    qr_code = client_service.get_client_qr_code(client_name)
    return QRCodeResponse(qr_code=qr_code)
