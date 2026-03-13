"""
WireGuard infrastructure backend built for the web API.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import ConfigurationError, ConflictError, IntegrationError, NotFoundError

logger = logging.getLogger(__name__)


@dataclass
class WireGuardClient:
    """WireGuard client parsed from the interface config."""

    name: str
    public_key: str
    ip_address: str
    allowed_ips: str
    ipv6_address: str | None = None
    config_path: Path | None = None


@dataclass
class WireGuardStats:
    """Runtime statistics from `wg show`."""

    public_key: str
    endpoint: str | None = None
    allowed_ips: str | None = None
    last_handshake: datetime | None = None
    bytes_received: int = 0
    bytes_sent: int = 0


@dataclass
class CreatedWireGuardClient:
    """Result of creating a client in the WireGuard backend."""

    client: WireGuardClient
    config_content: str


@dataclass
class DeletedWireGuardClient:
    """Snapshot used to compensate failed delete flows."""

    client: WireGuardClient
    peer_block: str
    config_content: str | None


class WireGuardBackend:
    """Infrastructure adapter for WireGuard files and runtime commands."""

    def __init__(self) -> None:
        self.interface = settings.wireguard_interface
        self.config_path = settings.wireguard_config_path
        self.client_config_dir = settings.wireguard_client_config_dir
        try:
            self.client_config_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ConfigurationError(
                f"Unable to access client config directory: {self.client_config_dir}"
            ) from exc

    def list_clients(self) -> list[WireGuardClient]:
        """Return clients derived from the WireGuard config."""
        return [entry["client"] for entry in self._parse_client_entries().values()]

    def get_client(self, client_name: str) -> WireGuardClient:
        """Return a single client derived from the WireGuard config."""
        entry = self._parse_client_entries().get(client_name)
        if not entry:
            raise NotFoundError("Client not found")
        return entry["client"]

    def get_client_config(self, client_name: str) -> str:
        """Return the stored client config content."""
        config_path = self.client_config_dir / f"{client_name}.conf"
        if not config_path.exists():
            raise NotFoundError("Client configuration file not found")
        return config_path.read_text(encoding="utf-8")

    def create_client(self, client_name: str, dns: str) -> CreatedWireGuardClient:
        """Create WireGuard config state for a new client."""
        if client_name in self._parse_client_entries():
            raise ConflictError("Client with this name already exists")

        server_context = self._read_server_context()
        octet = self._find_next_available_octet()
        client_private_key = self._run(["wg", "genkey"]).stdout.strip()
        client_public_key = self._run(
            ["wg", "pubkey"], input_text=client_private_key
        ).stdout.strip()
        preshared_key = self._run(["wg", "genpsk"]).stdout.strip()

        allowed_ips = f"10.7.0.{octet}/32"
        ipv6_address = None
        if server_context["has_ipv6"]:
            ipv6_address = f"fddd:2c4:2c4:2c4::{octet}"
            allowed_ips = f"{allowed_ips}, {ipv6_address}/128"

        peer_block = "\n".join(
            [
                f"# BEGIN_PEER {client_name}",
                "[Peer]",
                f"PublicKey = {client_public_key}",
                f"PresharedKey = {preshared_key}",
                f"AllowedIPs = {allowed_ips}",
                f"# END_PEER {client_name}",
                "",
            ]
        )

        client_config = "\n".join(
            self._build_client_config_lines(
                octet=octet,
                dns=dns,
                client_private_key=client_private_key,
                server_public_key=server_context["server_public_key"],
                preshared_key=preshared_key,
                endpoint=server_context["endpoint"],
                port=server_context["port"],
                ipv6_address=ipv6_address,
            )
        )
        config_path = self.client_config_dir / f"{client_name}.conf"

        self._append_peer_block(peer_block)
        try:
            config_path.write_text(client_config, encoding="utf-8")
            self._activate_peer(peer_block)
        except Exception as exc:
            self._remove_peer_block(client_name)
            if config_path.exists():
                config_path.unlink()
            raise IntegrationError("Failed to create WireGuard client") from exc

        client = WireGuardClient(
            name=client_name,
            public_key=client_public_key,
            ip_address=f"10.7.0.{octet}",
            ipv6_address=ipv6_address,
            allowed_ips=allowed_ips,
            config_path=config_path,
        )
        return CreatedWireGuardClient(client=client, config_content=client_config)

    def delete_client(self, client_name: str) -> DeletedWireGuardClient:
        """Delete WireGuard config state for a client."""
        entry = self._parse_client_entries().get(client_name)
        if not entry:
            raise NotFoundError("Client not found")

        client = entry["client"]
        peer_block = entry["peer_block"]
        config_path = self.client_config_dir / f"{client_name}.conf"
        config_content = None
        if config_path.exists():
            config_content = config_path.read_text(encoding="utf-8")

        self._remove_live_peer(client.public_key)
        self._remove_peer_block(client_name)
        if config_path.exists():
            config_path.unlink()

        return DeletedWireGuardClient(
            client=client,
            peer_block=peer_block,
            config_content=config_content,
        )

    def restore_client(self, snapshot: DeletedWireGuardClient) -> None:
        """Restore a previously deleted client."""
        if snapshot.client.name not in self._parse_client_entries():
            self._append_peer_block(snapshot.peer_block)

        if snapshot.config_content is not None:
            config_path = self.client_config_dir / f"{snapshot.client.name}.conf"
            config_path.write_text(snapshot.config_content, encoding="utf-8")

        self._activate_peer(snapshot.peer_block)

    def get_client_stats(self) -> dict[str, WireGuardStats]:
        """Collect runtime statistics indexed by public key."""
        try:
            result = self._run(["wg", "show", self.interface])
        except IntegrationError:
            logger.warning(
                "Failed to read WireGuard runtime stats",
                extra={"event": "wireguard.stats_unavailable"},
            )
            return {}

        stats: dict[str, WireGuardStats] = {}
        current_peer: str | None = None

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue

            if line.startswith("peer: "):
                current_peer = line.removeprefix("peer: ").strip()
                stats[current_peer] = WireGuardStats(public_key=current_peer)
                continue

            if not current_peer:
                continue

            peer_stats = stats[current_peer]
            if line.startswith("allowed ips: "):
                peer_stats.allowed_ips = line.removeprefix("allowed ips: ").strip()
            elif line.startswith("endpoint: "):
                endpoint = line.removeprefix("endpoint: ").strip()
                peer_stats.endpoint = None if endpoint == "(none)" else endpoint
            elif line.startswith("latest handshake: "):
                peer_stats.last_handshake = self._parse_relative_handshake(
                    line.removeprefix("latest handshake: ").strip()
                )
            elif line.startswith("transfer: "):
                received, sent = self._parse_transfer(line.removeprefix("transfer: ").strip())
                peer_stats.bytes_received = received
                peer_stats.bytes_sent = sent

        return stats

    def _run(
        self,
        command: list[str],
        *,
        input_text: str | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                input=input_text,
                text=True,
                capture_output=True,
                check=check,
            )
        except FileNotFoundError as exc:
            raise IntegrationError(f"Command not found: {command[0]}") from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() if exc.stderr else "unknown error"
            raise IntegrationError(
                f"Command failed: {' '.join(command)}",
                details={"stderr": stderr},
            ) from exc

    def _read_server_context(self) -> dict[str, str | bool]:
        self._ensure_server_config_exists()
        lines = self.config_path.read_text(encoding="utf-8").splitlines()

        endpoint = "127.0.0.1"
        port = "51820"
        server_private_key = ""
        has_ipv6 = False
        in_interface = False

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            if line == "[Interface]":
                in_interface = True
                continue
            if line == "[Peer]":
                in_interface = False
            if line.startswith("# ENDPOINT "):
                endpoint = line.split(" ", 2)[2].strip()
            if in_interface and line.startswith("ListenPort = "):
                port = line.split(" = ", 1)[1].strip()
            if in_interface and line.startswith("PrivateKey = "):
                server_private_key = line.split(" = ", 1)[1].strip()
            if in_interface and line.startswith("Address = ") and ":" in line:
                has_ipv6 = True

        if not server_private_key:
            raise ConfigurationError("WireGuard server private key was not found")

        server_public_key = self._run(
            ["wg", "pubkey"], input_text=server_private_key
        ).stdout.strip()

        return {
            "endpoint": endpoint,
            "port": port,
            "server_public_key": server_public_key,
            "has_ipv6": has_ipv6,
        }

    def _parse_client_entries(self) -> dict[str, dict[str, WireGuardClient | str]]:
        self._ensure_server_config_exists()
        lines = self.config_path.read_text(encoding="utf-8").splitlines()
        entries: dict[str, dict[str, WireGuardClient | str]] = {}

        index = 0
        while index < len(lines):
            line = lines[index]
            if not line.startswith("# BEGIN_PEER "):
                index += 1
                continue

            client_name = line.split(" ", 2)[2].strip()
            block_lines = [line]
            index += 1
            while index < len(lines):
                block_lines.append(lines[index])
                if lines[index].startswith(f"# END_PEER {client_name}"):
                    break
                index += 1

            peer_block = "\n".join(block_lines).strip() + "\n"
            client = self._parse_client_block(client_name, peer_block)
            entries[client_name] = {"client": client, "peer_block": peer_block}
            index += 1

        return entries

    def _parse_client_block(self, client_name: str, peer_block: str) -> WireGuardClient:
        public_key = self._extract_required_value(peer_block, "PublicKey")
        allowed_ips = self._extract_required_value(peer_block, "AllowedIPs")
        ip_address = self._extract_ipv4_address(allowed_ips)
        ipv6_address = self._extract_ipv6_address(allowed_ips)
        return WireGuardClient(
            name=client_name,
            public_key=public_key,
            ip_address=ip_address,
            allowed_ips=allowed_ips,
            ipv6_address=ipv6_address,
            config_path=self.client_config_dir / f"{client_name}.conf",
        )

    def _extract_required_value(self, block: str, key: str) -> str:
        match = re.search(rf"^{key} = (.+)$", block, re.MULTILINE)
        if not match:
            raise ConfigurationError(f"Unable to parse {key} from WireGuard config")
        return match.group(1).strip()

    def _extract_ipv4_address(self, allowed_ips: str) -> str:
        for item in allowed_ips.split(","):
            item = item.strip()
            if "." in item:
                return item.split("/", 1)[0]
        raise ConfigurationError("Unable to determine IPv4 address for peer")

    def _extract_ipv6_address(self, allowed_ips: str) -> str | None:
        for item in allowed_ips.split(","):
            item = item.strip()
            if ":" in item:
                return item.split("/", 1)[0]
        return None

    def _find_next_available_octet(self) -> int:
        occupied = {
            int(client.ip_address.rsplit(".", 1)[1])
            for client in self.list_clients()
            if client.ip_address.startswith("10.7.0.")
        }
        for octet in range(2, 255):
            if octet not in occupied:
                return octet
        raise ConflictError("WireGuard subnet is full")

    def _build_client_config_lines(
        self,
        *,
        octet: int,
        dns: str,
        client_private_key: str,
        server_public_key: str,
        preshared_key: str,
        endpoint: str,
        port: str,
        ipv6_address: str | None,
    ) -> list[str]:
        lines = [
            "[Interface]",
            f"Address = 10.7.0.{octet}/24",
        ]
        if ipv6_address:
            lines.append(f"Address = {ipv6_address}/64")
        lines.extend(
            [
                f"DNS = {dns}",
                f"PrivateKey = {client_private_key}",
                "",
                "[Peer]",
                f"PublicKey = {server_public_key}",
                f"PresharedKey = {preshared_key}",
                "AllowedIPs = 0.0.0.0/0, ::/0",
                f"Endpoint = {endpoint}:{port}",
                "PersistentKeepalive = 25",
                "",
            ]
        )
        return lines

    def _append_peer_block(self, peer_block: str) -> None:
        with self.config_path.open("a", encoding="utf-8") as config_file:
            config_file.write(peer_block)

    def _remove_peer_block(self, client_name: str) -> None:
        entries = self._parse_client_entries()
        entry = entries.get(client_name)
        if not entry:
            raise NotFoundError("Client not found")

        server_config = self.config_path.read_text(encoding="utf-8")
        updated = server_config.replace(entry["peer_block"], "")
        self.config_path.write_text(updated, encoding="utf-8")

    def _activate_peer(self, peer_block: str) -> None:
        peer_config = self._strip_peer_markers(peer_block)
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".conf", delete=False, encoding="utf-8"
            ) as temp_file:
                temp_file.write(peer_config)
                temp_file.flush()
                self._run(["wg", "addconf", self.interface, temp_file.name])
        except IntegrationError:
            self._reload_interface()
        finally:
            if "temp_file" in locals():
                try:
                    os.unlink(temp_file.name)
                except OSError:
                    logger.warning(
                        "Failed to remove temporary WireGuard peer file",
                        extra={"event": "wireguard.tempfile_cleanup_failed"},
                    )

    def _remove_live_peer(self, public_key: str) -> None:
        try:
            self._run(["wg", "set", self.interface, "peer", public_key, "remove"])
        except IntegrationError:
            self._reload_interface()

    def _reload_interface(self) -> None:
        self._run(["systemctl", "reload", f"wg-quick@{self.interface}.service"])

    def _strip_peer_markers(self, peer_block: str) -> str:
        lines = [
            line
            for line in peer_block.splitlines()
            if not line.startswith("# BEGIN_PEER ") and not line.startswith("# END_PEER ")
        ]
        return "\n".join(lines).strip() + "\n"

    def _ensure_server_config_exists(self) -> None:
        if not self.config_path.exists():
            raise ConfigurationError(
                f"WireGuard config not found: {self.config_path}"
            )

    def _parse_relative_handshake(self, value: str) -> datetime | None:
        if value == "never":
            return None

        total = timedelta()
        for amount, unit in re.findall(
            r"(\d+)\s+(second|minute|hour|day|week|month|year)s?", value
        ):
            amount_int = int(amount)
            if unit == "second":
                total += timedelta(seconds=amount_int)
            elif unit == "minute":
                total += timedelta(minutes=amount_int)
            elif unit == "hour":
                total += timedelta(hours=amount_int)
            elif unit == "day":
                total += timedelta(days=amount_int)
            elif unit == "week":
                total += timedelta(weeks=amount_int)
            elif unit == "month":
                total += timedelta(days=30 * amount_int)
            elif unit == "year":
                total += timedelta(days=365 * amount_int)

        if not total:
            return None
        return datetime.now(timezone.utc).replace(tzinfo=None) - total

    def _parse_transfer(self, value: str) -> tuple[int, int]:
        parts = value.split(", ")
        if len(parts) != 2:
            return 0, 0

        received_part = parts[0].removesuffix(" received")
        sent_part = parts[1].removesuffix(" sent")
        received_value, received_unit = received_part.split()
        sent_value, sent_unit = sent_part.split()
        return (
            self._convert_to_bytes(float(received_value), received_unit),
            self._convert_to_bytes(float(sent_value), sent_unit),
        )

    def _convert_to_bytes(self, value: float, unit: str) -> int:
        unit = unit.upper()
        if unit == "B":
            return int(value)
        if unit == "KIB":
            return int(value * 1024)
        if unit == "MIB":
            return int(value * 1024 * 1024)
        if unit == "GIB":
            return int(value * 1024 * 1024 * 1024)
        return int(value)
