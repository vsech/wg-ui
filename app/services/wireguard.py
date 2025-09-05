"""
WireGuard service for client management
"""
import os
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict
from sqlalchemy.orm import Session

from app.models.database import Client
from app.models.schemas import ClientCreate, ClientResponse, ClientConfig
from app.services.qr_generator import QRCodeService
from wg_installer import WireGuardClientManager


class WireGuardService:
    """WireGuard service class"""

    def __init__(self):
        self.wg_manager = WireGuardClientManager()
        self.qr_service = QRCodeService()

    def get_all_clients(self, db: Session) -> List[ClientResponse]:
        """Get all WireGuard clients"""
        wg_clients = self.wg_manager.get_client_list()

        db_clients = []
        for client_name in wg_clients:
            db_client = db.query(Client).filter(
                Client.name == client_name).first()
            if not db_client:
                # Create new client record in database
                ip_address = f"10.7.0.{len(db_clients) + 2}"
                db_client = Client(
                    name=client_name,
                    public_key="",
                    ip_address=ip_address
                )
                db.add(db_client)
                db.commit()
                db.refresh(db_client)

            db_clients.append(ClientResponse.from_orm(db_client))

        return db_clients

    def create_client(self, db: Session, client_data: ClientCreate) -> ClientConfig:
        """Create new WireGuard client"""
        if self.wg_manager.client_exists(client_data.name):
            raise ValueError("Client with this name already exists")

        # Create client configuration using WireGuard manager
        config_path, client_info = self.wg_manager.create_client_config(
            client_data.name,
            client_data.dns,
            self.wg_manager.server.server_ipv6
        )

        # Read configuration file
        with open(config_path, 'r', encoding='utf-8') as f:
            config_content = f.read()

        # Generate QR code
        qr_code_data = self.qr_service.generate_qr_code(config_content)

        # Save client to database
        db_client = Client(
            name=client_data.name,
            public_key=client_info['public_key'],
            ip_address=f"10.7.0.{client_info['octet']}"
        )
        db.add(db_client)
        db.commit()

        # Reload WireGuard configuration
        self._reload_wireguard_config(client_info)

        return ClientConfig(
            name=client_data.name,
            config=config_content,
            qr_code=qr_code_data
        )

    def delete_client(self, db: Session, client_name: str) -> None:
        """Delete WireGuard client"""
        if not self.wg_manager.client_exists(client_name):
            raise ValueError("Client not found")

        # Remove client from WireGuard configuration
        self.wg_manager.remove_client_from_config(client_name)

        # Remove client from database
        db_client = db.query(Client).filter(Client.name == client_name).first()
        if db_client:
            db.delete(db_client)
            db.commit()

        # Remove configuration file
        config_path = Path(self.wg_manager.script_dir) / f"{client_name}.conf"
        if config_path.exists():
            config_path.unlink()

    def get_client_qr_code(self, client_name: str) -> str:
        """Generate QR code for existing client"""
        if not self.wg_manager.client_exists(client_name):
            raise ValueError("Client not found")

        config_path = Path(self.wg_manager.script_dir) / f"{client_name}.conf"
        if not config_path.exists():
            raise ValueError("Client configuration file not found")

        with open(config_path, 'r', encoding='utf-8') as f:
            config_content = f.read()

        return self.qr_service.generate_qr_code(config_content)

    def _reload_wireguard_config(self, client_info: Dict) -> None:
        """Reload WireGuard configuration after adding client"""
        try:
            peer_config = f"""[Peer]
PublicKey = {client_info['public_key']}
PresharedKey = {client_info['psk']}
AllowedIPs = 10.7.0.{client_info['octet']}/32"""

            if self.wg_manager.server.server_ipv6:
                peer_config += f", fddd:2c4:2c4:2c4::{client_info['octet']}/128"

            with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as temp_file:
                temp_file.write(peer_config)
                temp_file.flush()
                self.wg_manager.run_command(
                    ["wg", "addconf", "wg0", temp_file.name])
                os.unlink(temp_file.name)
        except (subprocess.CalledProcessError, OSError, FileNotFoundError):
            self.wg_manager.run_command(
                ["systemctl", "reload", "wg-quick@wg0.service"])
