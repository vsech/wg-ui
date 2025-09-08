"""
Client management routes
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.database import User
from app.models.schemas import ClientCreate, ClientResponse, ClientConfig, QRCodeResponse, MessageResponse
from app.services.wireguard import WireGuardService

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("/", response_model=List[ClientResponse])
async def get_clients(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of all WireGuard clients"""
    wg_service = WireGuardService()
    return wg_service.get_all_clients(db)


@router.post("/", response_model=ClientConfig)
async def create_client(
    client_data: ClientCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new WireGuard client"""
    wg_service = WireGuardService()
    try:
        return wg_service.create_client(db, client_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create client: {str(e)}"
        )


@router.delete("/{client_name}", response_model=MessageResponse)
async def delete_client(
    client_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a WireGuard client"""
    wg_service = WireGuardService()
    try:
        wg_service.delete_client(db, client_name)
        return MessageResponse(message=f"Client {client_name} deleted successfully")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete client: {str(e)}"
        )


@router.get("/{client_name}/config", response_model=ClientConfig)
async def get_client_config(
    client_name: str,
    current_user: User = Depends(get_current_user)
):
    """Get complete client configuration including config text and QR code"""
    wg_service = WireGuardService()
    try:
        return wg_service.get_client_config(client_name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get client configuration: {str(e)}"
        )


@router.get("/{client_name}/qr", response_model=QRCodeResponse)
async def get_client_qr(
    client_name: str,
    current_user: User = Depends(get_current_user)
):
    """Generate QR code for existing client configuration"""
    wg_service = WireGuardService()
    try:
        qr_code = wg_service.get_client_qr_code(client_name)
        return QRCodeResponse(qr_code=qr_code)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate QR code: {str(e)}"
        )
