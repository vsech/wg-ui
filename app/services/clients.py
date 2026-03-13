"""
Client application service.
"""
from __future__ import annotations

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import IntegrationError
from app.infrastructure.wireguard.backend import (
    CreatedWireGuardClient,
    DeletedWireGuardClient,
    WireGuardBackend,
    WireGuardClient,
    WireGuardStats,
)
from app.models.database import Client
from app.models.schemas import ClientConfig, ClientCreate, ClientResponse
from app.services.qr_generator import QRCodeService

logger = logging.getLogger(__name__)


class ClientService:
    """Coordinates WireGuard state and cached client metadata."""

    def __init__(
        self,
        *,
        db: Session,
        backend: WireGuardBackend,
        qr_service: QRCodeService | None = None,
    ) -> None:
        self.db = db
        self.backend = backend
        self.qr_service = qr_service or QRCodeService()

    def get_all_clients(self) -> list[ClientResponse]:
        """Return clients synchronized from the WireGuard config."""
        backend_clients = self.backend.list_clients()
        stats_by_key = self.backend.get_client_stats()
        responses: list[ClientResponse] = []

        metadata_by_name = {
            item.name: item for item in self.db.query(Client).all()
        }
        active_names = {client.name for client in backend_clients}

        for backend_client in backend_clients:
            metadata = metadata_by_name.get(backend_client.name)
            metadata = self._upsert_client_metadata(
                metadata=metadata,
                backend_client=backend_client,
                stats=stats_by_key.get(backend_client.public_key),
            )
            responses.append(ClientResponse.model_validate(metadata))

        for stale_name, stale_metadata in metadata_by_name.items():
            if stale_name not in active_names:
                self.db.delete(stale_metadata)

        self.db.commit()
        return responses

    def create_client(self, client_data: ClientCreate) -> ClientConfig:
        """Create a client in WireGuard and persist cache metadata."""
        created = self.backend.create_client(client_data.name, client_data.dns)

        try:
            self._upsert_client_metadata(
                metadata=self._get_metadata(created.client.name),
                backend_client=created.client,
                stats=None,
            )
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            self._compensate_create(created)
            raise IntegrationError("Failed to persist client metadata") from exc

        return ClientConfig(
            name=created.client.name,
            config=created.config_content,
            qr_code=self.qr_service.generate_qr_code(created.config_content),
        )

    def delete_client(self, client_name: str) -> None:
        """Delete a client and compensate on persistence failure."""
        snapshot = self.backend.delete_client(client_name)

        try:
            metadata = self._get_metadata(client_name)
            if metadata:
                self.db.delete(metadata)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            self._compensate_delete(snapshot)
            raise IntegrationError("Failed to delete client metadata") from exc

    def get_client_qr_code(self, client_name: str) -> str:
        """Return QR code for the stored client config."""
        config_content = self.backend.get_client_config(client_name)
        return self.qr_service.generate_qr_code(config_content)

    def get_client_config(self, client_name: str) -> ClientConfig:
        """Return config, QR code and cached/live runtime data for a client."""
        backend_client = self.backend.get_client(client_name)
        config_content = self.backend.get_client_config(client_name)
        stats = self.backend.get_client_stats().get(backend_client.public_key)

        metadata = self._upsert_client_metadata(
            metadata=self._get_metadata(client_name),
            backend_client=backend_client,
            stats=stats,
        )
        self.db.commit()

        return ClientConfig(
            name=backend_client.name,
            config=config_content,
            qr_code=self.qr_service.generate_qr_code(config_content),
            last_handshake=metadata.last_handshake,
            bytes_received=metadata.bytes_received,
            bytes_sent=metadata.bytes_sent,
        )

    def _upsert_client_metadata(
        self,
        *,
        metadata: Client | None,
        backend_client: WireGuardClient,
        stats: WireGuardStats | None,
    ) -> Client:
        if metadata is None:
            metadata = Client(
                name=backend_client.name,
                public_key=backend_client.public_key,
                ip_address=backend_client.ip_address,
                is_active=True,
            )
            self.db.add(metadata)

        metadata.name = backend_client.name
        metadata.public_key = backend_client.public_key
        metadata.ip_address = backend_client.ip_address
        metadata.is_active = True

        if stats:
            metadata.last_handshake = stats.last_handshake
            metadata.bytes_received = stats.bytes_received
            metadata.bytes_sent = stats.bytes_sent

        self.db.flush()
        return metadata

    def _get_metadata(self, client_name: str) -> Client | None:
        return self.db.query(Client).filter(Client.name == client_name).first()

    def _compensate_create(self, created: CreatedWireGuardClient) -> None:
        try:
            self.backend.delete_client(created.client.name)
        except Exception:
            logger.exception(
                "Create compensation failed",
                extra={"event": "clients.create_compensation_failed"},
            )

    def _compensate_delete(self, snapshot: DeletedWireGuardClient) -> None:
        try:
            self.backend.restore_client(snapshot)
        except Exception:
            logger.exception(
                "Delete compensation failed",
                extra={"event": "clients.delete_compensation_failed"},
            )
