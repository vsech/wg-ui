"""
WireGuard service for client management
"""
import os
import tempfile
import subprocess
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
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
        """Get all WireGuard clients with statistics"""
        wg_clients = self.wg_manager.get_client_list()
        wg_stats = self.get_wireguard_stats()

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

            # Update client statistics from WireGuard by matching IP addresses
            client_stats = None
            for pub_key, stats in wg_stats.items():
                allowed_ips = stats.get('allowed_ips', '')
                # Extract IP from allowed_ips (e.g., "10.7.0.2/32, fddd:2c4:2c4:2c4::2/128")
                if allowed_ips and db_client.ip_address in allowed_ips:
                    client_stats = stats
                    # Update the public key in database if it's missing
                    if not db_client.public_key:
                        db_client.public_key = pub_key
                    break

            if client_stats:
                db_client.last_handshake = client_stats['last_handshake']
                db_client.bytes_received = client_stats['bytes_received']
                db_client.bytes_sent = client_stats['bytes_sent']
                db.commit()

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
        config_path = self.wg_manager.client_config_dir / f"{client_name}.conf"
        if config_path.exists():
            config_path.unlink()

    def get_client_qr_code(self, client_name: str) -> str:
        """Generate QR code for existing client"""
        if not self.wg_manager.client_exists(client_name):
            raise ValueError("Client not found")

        config_path = self.wg_manager.client_config_dir / f"{client_name}.conf"
        if not config_path.exists():
            raise ValueError("Client configuration file not found")

        with open(config_path, 'r', encoding='utf-8') as f:
            config_content = f.read()

        return self.qr_service.generate_qr_code(config_content)

    def get_wireguard_stats(self) -> Dict[str, Dict]:
        """Get WireGuard statistics from system"""
        try:
            result = subprocess.run(['wg', 'show', 'wg0'], 
                                  capture_output=True, text=True, check=True)
            stats = {}
            current_peer = None
            
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith('peer:'):
                    # Extract public key
                    current_peer = line.split('peer: ')[1]
                    stats[current_peer] = {
                        'endpoint': None,
                        'allowed_ips': None,
                        'last_handshake': None,
                        'bytes_received': 0,
                        'bytes_sent': 0
                    }
                elif current_peer and line.startswith('allowed ips:'):
                    stats[current_peer]['allowed_ips'] = line.split('allowed ips: ')[1]
                elif current_peer and line.startswith('endpoint:'):
                    endpoint = line.split('endpoint: ')[1]
                    stats[current_peer]['endpoint'] = endpoint if endpoint != '(none)' else None
                elif current_peer and line.startswith('latest handshake:'):
                    # Parse handshake time - convert relative time to datetime
                    handshake_text = line.split('latest handshake: ')[1]
                    if 'ago' in handshake_text and handshake_text != 'never':
                        # For now, set to a recent time - in production you'd parse the relative time
                        stats[current_peer]['last_handshake'] = datetime.now()
                elif current_peer and line.startswith('transfer:'):
                    # Parse transfer data: "147.18 KiB received, 338.24 KiB sent"
                    transfer_text = line.split('transfer: ')[1]
                    parts = transfer_text.split(', ')
                    
                    if len(parts) >= 2:
                        # Parse received
                        received_part = parts[0].split(' received')[0]
                        received_value, received_unit = received_part.split()
                        received_bytes = self._convert_to_bytes(float(received_value), received_unit)
                        
                        # Parse sent
                        sent_part = parts[1].split(' sent')[0]
                        sent_value, sent_unit = sent_part.split()
                        sent_bytes = self._convert_to_bytes(float(sent_value), sent_unit)
                        
                        stats[current_peer]['bytes_received'] = received_bytes
                        stats[current_peer]['bytes_sent'] = sent_bytes
            
            return stats
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
            return {}

    def _convert_to_bytes(self, value: float, unit: str) -> int:
        """Convert data size to bytes"""
        unit = unit.upper()
        if unit == 'B':
            return int(value)
        elif unit == 'KIB':
            return int(value * 1024)
        elif unit == 'MIB':
            return int(value * 1024 * 1024)
        elif unit == 'GIB':
            return int(value * 1024 * 1024 * 1024)
        else:
            return int(value)

    def get_client_config(self, client_name: str, db: Session) -> ClientConfig:
        """Get complete client configuration including config text, QR code and statistics"""
        if not self.wg_manager.client_exists(client_name):
            raise ValueError("Client not found")

        config_path = self.wg_manager.client_config_dir / f"{client_name}.conf"
        if not config_path.exists():
            raise ValueError("Client configuration file not found")

        with open(config_path, 'r', encoding='utf-8') as f:
            config_content = f.read()

        qr_code_data = self.qr_service.generate_qr_code(config_content)

        # Get client from database for statistics
        db_client = db.query(Client).filter(Client.name == client_name).first()
        wg_stats = self.get_wireguard_stats()
        
        # Update statistics if available
        last_handshake = None
        bytes_received = 0
        bytes_sent = 0
        
        if db_client:
            # Update from live WireGuard stats by matching IP addresses
            for pub_key, stats in wg_stats.items():
                allowed_ips = stats.get('allowed_ips', '')
                if allowed_ips and db_client.ip_address in allowed_ips:
                    last_handshake = stats['last_handshake']
                    bytes_received = stats['bytes_received']
                    bytes_sent = stats['bytes_sent']
                    
                    # Update database
                    db_client.last_handshake = last_handshake
                    db_client.bytes_received = bytes_received
                    db_client.bytes_sent = bytes_sent
                    # Update public key if missing
                    if not db_client.public_key:
                        db_client.public_key = pub_key
                    db.commit()
                    break
            else:
                # Use database values if no live stats
                last_handshake = db_client.last_handshake
                bytes_received = db_client.bytes_received
                bytes_sent = db_client.bytes_sent

        return ClientConfig(
            name=client_name,
            config=config_content,
            qr_code=qr_code_data,
            last_handshake=last_handshake,
            bytes_received=bytes_received,
            bytes_sent=bytes_sent
        )

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
