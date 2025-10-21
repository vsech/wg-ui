#!/usr/bin/env python3
"""
WireGuard VPN Installer - Python Version
Based on the original bash script: https://github.com/Nyr/wireguard-install
"""

import os
import sys
import subprocess
import platform
import re
import shutil
import urllib.request
import tempfile
import tarfile
from pathlib import Path
from typing import Optional, List, Tuple
import argparse
from wg_const import Colors, SystemConfig, ServerConfig

class WireGuardBase:
    """Base class with common functionality for WireGuard operations"""

    def __init__(self):
        self.system = SystemConfig()
        self.script_dir = Path(__file__).parent.absolute()
        self.client_config_dir = Path("/opt/wg-ui/data")
        try:
            self.client_config_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            self.print_error(
                "Unable to access /opt/wg-ui/data. Run the installer with sufficient privileges.")
            sys.exit(1)
        self.wg_config_path = Path("/etc/wireguard/wg0.conf")

    def print_banner(self, text: str):
        """Print a formatted banner"""
        print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*50}{Colors.END}")
        print(f"{Colors.CYAN}{Colors.BOLD}{text:^50}{Colors.END}")
        print(f"{Colors.CYAN}{Colors.BOLD}{'='*50}{Colors.END}\n")

    def print_success(self, text: str):
        """Print success message"""
        print(f"{Colors.GREEN}✓ {text}{Colors.END}")

    def print_error(self, text: str):
        """Print error message"""
        print(f"{Colors.RED}✗ {text}{Colors.END}")

    def print_warning(self, text: str):
        """Print warning message"""
        print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

    def print_info(self, text: str):
        """Print info message"""
        print(f"{Colors.BLUE}ℹ {text}{Colors.END}")

    def run_command(self, command: List[str],
                    check: bool = True,
                    capture_output: bool = False,
                    input_text: str = None) -> subprocess.CompletedProcess:
        """Run a shell command"""
        try:
            if input_text:
                result = subprocess.run(
                    command,
                    check=check,
                    capture_output=capture_output,
                    text=True,
                    input=input_text
                )
            else:
                result = subprocess.run(
                    command,
                    check=check,
                    capture_output=capture_output,
                    text=True
                )
            return result
        except subprocess.CalledProcessError as e:
            if check:
                self.print_error(f"Command failed: {' '.join(command)}")
                sys.exit(1)
            return e

    def check_root(self):
        """Check if running as root"""
        if os.geteuid() != 0:
            self.print_error(
                "This installer needs to be run with superuser privileges.")
            sys.exit(1)

    def detect_os(self) -> Tuple[str, str]:
        """Detect operating system and version"""
        system = platform.system().lower()

        if system == "linux":
            # Try to read OS release file
            os_release_paths = [
                "/etc/os-release",
                "/etc/lsb-release",
                "/etc/debian_version",
                "/etc/redhat-release",
                "/etc/centos-release",
                "/etc/fedora-release",
                "/etc/almalinux-release",
                "/etc/rocky-release"
            ]

            for release_file in os_release_paths:
                if os.path.exists(release_file):
                    try:
                        with open(release_file, 'r') as f:
                            content = f.read()

                        if "ubuntu" in content.lower():
                            # Extract Ubuntu version
                            match = re.search(
                                r'VERSION_ID="?(\d+\.\d+)"?', content)
                            if match:
                                version = match.group(1).replace('.', '')
                                return "ubuntu", version
                        elif "debian" in content.lower():
                            # Check if it's testing/unstable
                            if "/sid" in content:
                                self.print_error(
                                    "Debian Testing and Debian Unstable are unsupported by this installer.")
                                sys.exit(1)

                            # Extract Debian version
                            match = re.search(r'VERSION_ID="?(\d+)"?', content)
                            if match:
                                return "debian", match.group(1)
                        elif any(x in content.lower() for x in ["almalinux", "rocky", "centos"]):
                            # Extract version from CentOS-like systems
                            match = re.search(r'(\d+)', content)
                            if match:
                                return "centos", match.group(1)
                        elif "fedora" in content.lower():
                            # Extract Fedora version
                            match = re.search(r'(\d+)', content)
                            if match:
                                return "fedora", match.group(1)
                    except Exception:
                        continue

            # Fallback to generic Linux
            return "linux", "unknown"
        else:
            self.print_error(f"Unsupported operating system: {system}")
            sys.exit(1)

    def check_os_compatibility(self):
        """Check if the detected OS is compatible"""
        if self.system.os_name == "ubuntu" and int(self.system.os_version) < 2204:
            self.print_error(
                "Ubuntu 22.04 or higher is required to use this installer.")
            sys.exit(1)
        elif self.system.os_name == "debian" and int(self.system.os_version) < 11:
            self.print_error(
                "Debian 11 or higher is required to use this installer.")
            sys.exit(1)
        elif self.system.os_name == "centos" and int(self.system.os_version) < 9:
            self.print_error(
                f"{self.system.os_name.title()} 9 or higher is required to use this installer."
            )
            sys.exit(1)

    def check_boringtun_requirement(self):
        """Check if BoringTun is needed"""
        # Check if running in container
        try:
            result = self.run_command(
                ["systemd-detect-virt", "-cq"], check=False, capture_output=True)
            if result.returncode == 0:
                # Running in container
                # Check if wireguard kernel module is available
                if os.path.exists("/proc/modules"):
                    with open("/proc/modules", 'r') as f:
                        if "wireguard" in f.read():
                            self.system.use_boringtun = False
                        else:
                            self.system.use_boringtun = True
                else:
                    self.system.use_boringtun = True
            else:
                self.system.use_boringtun = False
        except FileNotFoundError:
            self.system.use_boringtun = False

    def check_tun_device(self):
        """Check if TUN device is available (required for BoringTun)"""
        if self.system.use_boringtun:
            if not os.path.exists("/dev/net/tun"):
                self.print_error(
                    "The system does not have the TUN device available.")
                sys.exit(1)

            # Check if TUN device is accessible
            try:
                with open("/dev/net/tun", "r+b"):
                    pass
            except PermissionError:
                self.print_error(
                    "TUN device is not accessible. Check permissions.")
                sys.exit(1)

    def get_network_interfaces(self) -> Tuple[List[str], List[str]]:
        """Get available IPv4 and IPv6 addresses"""
        ipv4_addresses = []
        ipv6_addresses = []

        try:
            # Get IPv4 addresses
            result = self.run_command(
                ["ip", "-4", "addr", "show"], capture_output=True)
            for line in result.stdout.split('\n'):
                if 'inet ' in line:
                    match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', line)
                    if match and not line.strip().startswith('127.'):
                        ipv4_addresses.append(match.group(1))

            # Get IPv6 addresses
            result = self.run_command(
                ["ip", "-6", "addr", "show"], capture_output=True)
            for line in result.stdout.split('\n'):
                if 'inet6 ' in line and '::1' not in line:
                    match = re.search(r'inet6 ([0-9a-fA-F:]+)', line)
                    if match:
                        ipv6_addresses.append(match.group(1))

        except Exception as e:
            self.print_warning(f"Could not detect network interfaces: {e}")

        return ipv4_addresses, ipv6_addresses

    def get_public_ip(self) -> Optional[str]:
        """Get public IP address"""
        try:
            response = urllib.request.urlopen(
                "http://ip1.dynupdate.no-ip.com/", timeout=10)
            public_ip = response.read().decode('utf-8').strip()
            if re.match(r'^\d+\.\d+\.\d+\.\d+$', public_ip):
                return public_ip
        except Exception:
            pass
        return None

    def is_private_ip(self, ip: str) -> bool:
        """Check if IP address is private"""
        parts = ip.split('.')
        if len(parts) != 4:
            return False

        first = int(parts[0])
        second = int(parts[1])

        return (first == 10 or
                (first == 172 and 16 <= second <= 31) or
                (first == 192 and second == 168))

    def select_dns(self) -> str:
        """Let user select DNS server"""
        print("\nSelect a DNS server for the client:")
        print("   1) Default system resolvers")
        print("   2) Google")
        print("   3) 1.1.1.1")
        print("   4) OpenDNS")
        print("   5) Quad9")
        print("   6) AdGuard")
        print("   7) Specify custom resolvers")

        while True:
            try:
                choice = input("DNS server [1]: ").strip()
                if not choice:
                    choice = "1"

                if choice in ["1", "2", "3", "4", "5", "6", "7"]:
                    break
                else:
                    print(f"{choice}: invalid selection.")
            except KeyboardInterrupt:
                sys.exit(1)

        dns_servers = {
            "1": self.get_system_dns(),
            "2": "8.8.8.8, 8.8.4.4",
            "3": "1.1.1.1, 1.0.0.1",
            "4": "208.67.222.222, 208.67.220.220",
            "5": "9.9.9.9, 149.112.112.112",
            "6": "94.140.14.14, 94.140.15.15",
            "7": self.get_custom_dns()
        }

        return dns_servers[choice]

    def get_system_dns(self) -> str:
        """Get system DNS servers"""
        resolv_conf = "/etc/resolv.conf"
        if os.path.exists("/run/systemd/resolve/resolv.conf"):
            with open("/etc/resolv.conf", 'r') as f:
                if '127.0.0.53' in f.read():
                    resolv_conf = "/run/systemd/resolve/resolv.conf"

        dns_servers = []
        try:
            with open(resolv_conf, 'r') as f:
                for line in f:
                    if line.startswith('nameserver') and '127.0.0.53' not in line:
                        match = re.search(
                            r'nameserver\s+(\d+\.\d+\.\d+\.\d+)', line)
                        if match:
                            dns_servers.append(match.group(1))
        except Exception:
            pass

        if not dns_servers:
            dns_servers = ["8.8.8.8", "8.8.4.4"]

        return ", ".join(dns_servers)

    def get_custom_dns(self) -> str:
        """Get custom DNS servers from user input"""
        while True:
            try:
                dns_input = input(
                    "Enter DNS servers (one or more IPv4 addresses, separated by commas or spaces): ").strip()
                dns_servers = []

                for dns_ip in re.split(r'[,\s]+', dns_input):
                    dns_ip = dns_ip.strip()
                    if re.match(r'^\d+\.\d+\.\d+\.\d+$', dns_ip):
                        dns_servers.append(dns_ip)

                if dns_servers:
                    return ", ".join(dns_servers)
                else:
                    print("Invalid input.")
            except KeyboardInterrupt:
                sys.exit(1)

    def install_packages(self):
        """Install required packages based on OS"""
        self.print_info("Installing required packages...")

        if self.system.os_name in ["ubuntu", "debian"]:
            self.run_command(["apt-get", "update"])
            if self.system.use_boringtun:
                packages = ["qrencode", "ca-certificates",
                            "cron", "wireguard-tools"]
            else:
                packages = ["wireguard", "qrencode"]

            for package in packages:
                self.run_command(["apt-get", "install", "-y", package])

        elif self.system.os_name in ["centos", "fedora"]:
            if self.system.os_name == "centos":
                self.run_command(["dnf", "install", "-y", "epel-release"])

            if self.system.use_boringtun:
                packages = ["wireguard-tools", "qrencode",
                            "ca-certificates", "tar", "cronie"]
            else:
                packages = ["wireguard-tools", "qrencode"]

            for package in packages:
                self.run_command(["dnf", "install", "-y", package])

    def install_boringtun(self):
        """Install BoringTun if needed"""
        if not self.system.use_boringtun:
            return

        self.print_info("Installing BoringTun...")

        # Download and install BoringTun
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Download BoringTun
                url = "https://wg.nyr.be/1/latest/download"
                response = urllib.request.urlopen(url)

                # Save to temporary file
                tar_path = os.path.join(temp_dir, "boringtun.tar.gz")
                with open(tar_path, 'wb') as f:
                    f.write(response.read())

                # Extract
                with tarfile.open(tar_path, 'r:gz') as tar:
                    tar.extractall(temp_dir)

                # Find and install binary
                for root, dirs, files in os.walk(temp_dir):
                    if 'boringtun' in files:
                        boringtun_path = os.path.join(root, 'boringtun')
                        shutil.copy2(boringtun_path,
                                     '/usr/local/sbin/boringtun')
                        os.chmod('/usr/local/sbin/boringtun', 0o755)
                        break

                # Configure wg-quick to use BoringTun
                os.makedirs(
                    '/etc/systemd/system/wg-quick@wg0.service.d/', exist_ok=True)
                with open('/etc/systemd/system/wg-quick@wg0.service.d/boringtun.conf', 'w') as f:
                    f.write("[Service]\n")
                    f.write(
                        "Environment=WG_QUICK_USERSPACE_IMPLEMENTATION=boringtun\n")
                    f.write("Environment=WG_SUDO=1\n")

                self.print_success("BoringTun installed successfully")

        except Exception as e:
            self.print_error(f"Failed to install BoringTun: {e}")
            sys.exit(1)

    def generate_wireguard_keys(self) -> Tuple[str, str]:
        """Generate WireGuard private and public keys"""
        try:
            # Generate private key
            result = self.run_command(["wg", "genkey"], capture_output=True)
            private_key = result.stdout.strip()

            # Generate public key
            result = self.run_command(
                ["wg", "pubkey"], input_text=private_key, capture_output=True)
            public_key = result.stdout.strip()

            return private_key, public_key
        except Exception as e:
            self.print_error(f"Failed to generate WireGuard keys: {e}")
            sys.exit(1)

    def create_server_config(self, private_key: str, port: int, ipv6: Optional[str] = None):
        """Create WireGuard server configuration"""
        config_content = f"""# Do not alter the commented lines
# They are used by wireguard-install
# ENDPOINT {self.server.public_ip or self.server.server_ip}

[Interface]
Address = 10.7.0.1/24"""

        if ipv6:
            config_content += "\nAddress = fddd:2c4:2c4:2c4::1/64"

        config_content += f"""
PrivateKey = {private_key}
ListenPort = {port}
"""

        # Write configuration
        os.makedirs('/etc/wireguard', exist_ok=True)
        with open('/etc/wireguard/wg0.conf', 'a', encoding='utf-8') as f:
            f.write(config_content)

        # Set proper permissions
        os.chmod('/etc/wireguard/wg0.conf', 0o600)

    def setup_firewall(self, port: int):
        """Setup firewall rules"""
        self.print_info("Setting up firewall rules...")

        # Check if firewalld is active
        try:
            result = self.run_command(
                ["systemctl", "is-active", "--quiet", "firewalld.service"], check=False)
            if result.returncode == 0:
                self.setup_firewalld(port)
            else:
                self.setup_iptables(port)
        except Exception:
            self.setup_iptables(port)

    def setup_firewalld(self, port: int):
        """Setup firewalld rules"""
        try:
            # Add port
            self.run_command(["firewall-cmd", "--add-port", f"{port}/udp"])
            self.run_command(["firewall-cmd", "--permanent",
                             "--add-port", f"{port}/udp"])

            # Add trusted sources
            self.run_command(["firewall-cmd", "--zone=trusted",
                             "--add-source", "10.7.0.0/24"])
            self.run_command(["firewall-cmd", "--permanent",
                             "--zone=trusted", "--add-source", "10.7.0.0/24"])

            # Set NAT
            self.run_command(["firewall-cmd", "--direct", "--add-rule", "ipv4", "nat", "POSTROUTING", "0",
                             "-s", "10.7.0.0/24", "!", "-d", "10.7.0.0/24", "-j", "SNAT", "--to", self.server.server_ip])
            self.run_command(["firewall-cmd", "--permanent", "--direct", "--add-rule", "ipv4", "nat", "POSTROUTING",
                             "0", "-s", "10.7.0.0/24", "!", "-d", "10.7.0.0/24", "-j", "SNAT", "--to", self.server.server_ip])

            self.print_success("Firewalld rules configured")
        except Exception as e:
            self.print_warning(f"Failed to configure firewalld: {e}")

    def setup_iptables(self, port: int):
        """Setup iptables rules"""
        try:
            # Create iptables service
            service_content = f"""[Unit]
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/sbin/iptables -w 5 -t nat -A POSTROUTING -s 10.7.0.0/24 ! -d 10.7.0.0/24 -j SNAT --to {self.server.server_ip}
ExecStart=/sbin/iptables -w 5 -I INPUT -p udp --dport {port} -j ACCEPT
ExecStart=/sbin/iptables -w 5 -I FORWARD -s 10.7.0.0/24 -j ACCEPT
ExecStart=/sbin/iptables -w 5 -I FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT
ExecStop=/sbin/iptables -w 5 -t nat -D POSTROUTING -s 10.7.0.0/24 ! -d 10.7.0.0/24 -j SNAT --to {self.server.server_ip}
ExecStop=/sbin/iptables -w 5 -D INPUT -p udp --dport {port} -j ACCEPT
ExecStop=/sbin/iptables -w 5 -D FORWARD -s 10.7.0.0/24 -j ACCEPT
ExecStop=/sbin/iptables -w 5 -D FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""

            with open('/etc/systemd/system/wg-iptables.service', 'w') as f:
                f.write(service_content)

            # Enable and start service
            self.run_command(
                ["systemctl", "enable", "--now", "wg-iptables.service"])
            self.print_success("Iptables rules configured")

        except Exception as e:
            self.print_warning(f"Failed to configure iptables: {e}")

    def enable_ip_forwarding(self, ipv6: Optional[str] = None):
        """Enable IP forwarding"""
        try:
            # IPv4 forwarding
            with open('/etc/sysctl.d/99-wireguard-forward.conf', 'w') as f:
                f.write('net.ipv4.ip_forward=1\n')
                if ipv6:
                    f.write('net.ipv6.conf.all.forwarding=1\n')

            # Enable immediately
            with open('/proc/sys/net/ipv4/ip_forward', 'w') as f:
                f.write('1')

            if ipv6:
                with open('/proc/sys/net/ipv6/conf/all/forwarding', 'w') as f:
                    f.write('1')

            self.print_success("IP forwarding enabled")
        except Exception as e:
            self.print_warning(f"Failed to enable IP forwarding: {e}")

    def start_wireguard_service(self):
        """Start and enable WireGuard service"""
        try:
            self.run_command(
                ["systemctl", "enable", "--now", "wg-quick@wg0.service"])
            self.print_success("WireGuard service started")
        except Exception as e:
            self.print_error(f"Failed to start WireGuard service: {e}")
            sys.exit(1)

    def generate_qr_code(self, config_path: str):
        """Generate QR code for client configuration"""
        try:
            # Read the configuration file content
            with open(config_path, 'r', encoding='utf-8') as f:
                config_content = f.read()

            # Generate QR code from file content, not file path
            self.run_command(["qrencode", "-t", "ANSI256UTF8"],
                             input_text=config_content)
            print("\n↑ That is a QR code containing the client configuration.")
        except Exception as e:
            self.print_warning(f"Could not generate QR code: {e}")

    def install_wireguard(self):
        """Main installation function"""
        self.print_banner("WireGuard VPN Installer")

        # Check prerequisites
        self.check_root()
        self.system.os_name, self.system.os_version = self.detect_os()
        self.check_os_compatibility()
        self.check_boringtun_requirement()

        if self.system.use_boringtun:
            self.check_tun_device()

        # Get network information
        ipv4_addresses, ipv6_addresses = self.get_network_interfaces()

        if not ipv4_addresses:
            self.print_error("No IPv4 addresses found")
            sys.exit(1)

        # Select server IP
        if len(ipv4_addresses) == 1:
            self.server.server_ip = ipv4_addresses[0]
        else:
            print("\nWhich IPv4 address should be used?")
            for i, ip in enumerate(ipv4_addresses, 1):
                print(f"   {i}) {ip}")

            while True:
                try:
                    choice = input("IPv4 address [1]: ").strip()
                    if not choice:
                        choice = "1"

                    choice_num = int(choice)
                    if 1 <= choice_num <= len(ipv4_addresses):
                        self.server.server_ip = ipv4_addresses[choice_num - 1]
                        break
                    else:
                        print(f"{choice}: invalid selection.")
                except (ValueError, KeyboardInterrupt):
                    print("Invalid input.")
                    if KeyboardInterrupt:
                        sys.exit(1)

        # Check if behind NAT
        if self.is_private_ip(self.server.server_ip):
            print(
                "\nThis server is behind NAT. What is the public IPv4 address or hostname?")
            public_ip = self.get_public_ip()
            if public_ip:
                print(f"Detected public IP: {public_ip}")

            while True:
                try:
                    user_input = input(
                        f"Public IPv4 address / hostname [{public_ip}]: ").strip()
                    if not user_input and public_ip:
                        self.server.public_ip = public_ip
                        break
                    elif user_input:
                        self.server.public_ip = user_input
                        break
                    else:
                        print("Invalid input.")
                except KeyboardInterrupt:
                    sys.exit(1)
        else:
            self.server.public_ip = self.server.server_ip

        # Select IPv6 (if available)
        self.server.server_ipv6 = None
        if ipv6_addresses:
            if len(ipv6_addresses) == 1:
                self.server.server_ipv6 = ipv6_addresses[0]
            else:
                print("\nWhich IPv6 address should be used?")
                for i, ip in enumerate(ipv6_addresses, 1):
                    print(f"   {i}) {ip}")

                while True:
                    try:
                        choice = input("IPv6 address [1]: ").strip()
                        if not choice:
                            choice = "1"

                        choice_num = int(choice)
                        if 1 <= choice_num <= len(ipv6_addresses):
                            self.server.server_ipv6 = ipv6_addresses[choice_num - 1]
                            break
                        else:
                            print(f"{choice}: invalid selection.")
                    except (ValueError, KeyboardInterrupt):
                        print("Invalid input.")
                        if KeyboardInterrupt:
                            sys.exit(1)

        # Get port
        while True:
            try:
                port_input = input(
                    "\nWhat port should WireGuard listen on? [51820]: ").strip()
                if not port_input:
                    self.server.port = 51820
                    break

                port_num = int(port_input)
                if 1 <= port_num <= 65535:
                    self.server.port = port_num
                    break
                else:
                    print(f"{port_input}: invalid port.")
            except (ValueError, KeyboardInterrupt):
                print("Invalid input.")
                if KeyboardInterrupt:
                    sys.exit(1)

        # Get client name
        while True:
            try:
                client_name = input(
                    "\nEnter a name for the first client [client]: ").strip()
                if not client_name:
                    client_name = "client"

                # Sanitize client name
                client_name = re.sub(r'[^0-9a-zA-Z_-]', '_', client_name)[:15]
                break
            except KeyboardInterrupt:
                sys.exit(1)

        # Get DNS preference
        dns = self.select_dns()

        # Confirm installation
        print("\nWireGuard installation is ready to begin.")
        input("Press Enter to continue...")

        # Install packages
        self.install_packages()

        # Install BoringTun if needed
        if self.system.use_boringtun:
            self.install_boringtun()

        # Generate keys
        server_private_key, _ = self.generate_wireguard_keys()

        # Create server configuration
        self.create_server_config(
            server_private_key, self.server.port, self.server.server_ipv6)

        # Enable IP forwarding
        self.enable_ip_forwarding(self.server.server_ipv6)

        # Setup firewall
        self.setup_firewall(self.server.port)

        # Create first client
        client_config_path = self.create_initial_client_config(
            client_name, dns, self.server.server_ipv6
        )

        # Start service
        self.start_wireguard_service()

        # Generate QR code
        self.generate_qr_code(client_config_path)

        print(f"\nFinished!")
        print(
            f"The client configuration is available in: {client_config_path}")
        print("New clients can be added by running this script again.")

    def remove_wireguard(self):
        """Remove WireGuard completely"""
        while True:
            try:
                confirm = input(
                    "Confirm WireGuard removal? [y/N]: ").strip().lower()
                if confirm in ['y', 'yes']:
                    break
                elif confirm in ['n', 'no', '']:
                    return
                else:
                    print("Invalid input.")
            except KeyboardInterrupt:
                return

        self.print_info("Removing WireGuard...")

        try:
            # Stop services
            self.run_command(
                ["systemctl", "stop", "wg-quick@wg0.service"], check=False)
            self.run_command(
                ["systemctl", "disable", "wg-quick@wg0.service"], check=False)

            # Remove configuration files
            if os.path.exists('/etc/wireguard'):
                shutil.rmtree('/etc/wireguard')

            # Remove systemd files
            for file_path in [
                '/etc/systemd/system/wg-iptables.service',
                '/etc/systemd/system/wg-quick@wg0.service.d/boringtun.conf'
            ]:
                if os.path.exists(file_path):
                    os.remove(file_path)

            # Remove sysctl configuration
            if os.path.exists('/etc/sysctl.d/99-wireguard-forward.conf'):
                os.remove('/etc/sysctl.d/99-wireguard-forward.conf')

            # Remove BoringTun if installed
            if os.path.exists('/usr/local/sbin/boringtun'):
                os.remove('/usr/local/sbin/boringtun')

            if os.path.exists('/usr/local/sbin/boringtun-upgrade'):
                os.remove('/usr/local/sbin/boringtun-upgrade')

            self.print_success("WireGuard removed successfully!")

        except Exception as e:
            self.print_error(f"Failed to remove WireGuard: {e}")


class WireGuardInstaller(WireGuardBase):
    """Class for WireGuard installation and removal operations"""

    def __init__(self):
        super().__init__()
        # Server configuration
        self.server = ServerConfig()

    def create_initial_client_config(self, client_name: str, dns: str, ipv6: Optional[str] = None) -> str:
        """Create initial client configuration during installation"""
        # Generate client keys
        client_private_key, client_public_key = self.generate_wireguard_keys()
        psk = self.run_command(
            ["wg", "genpsk"], capture_output=True).stdout.strip()

        # Add client to server config
        server_config = f"""
# BEGIN_PEER {client_name}
[Peer]
PublicKey = {client_public_key}
PresharedKey = {psk}
AllowedIPs = 10.7.0.2/32"""

        if ipv6:
            server_config += ", fddd:2c4:2c4:2c4::2/128"

        server_config += f"""
# END_PEER {client_name}
"""

        # Append to server config
        with open('/etc/wireguard/wg0.conf', 'a', encoding='utf-8') as f:
            f.write(server_config)

        # Get server public key
        server_private_key = self.get_server_private_key()
        server_public_key = self.run_command(
            ["wg", "pubkey"], input_text=server_private_key, capture_output=True).stdout.strip()

        # Create client config
        client_config = f"""[Interface]
Address = 10.7.0.2/24"""

        if ipv6:
            client_config += "\nAddress = fddd:2c4:2c4:2c4::2/64"

        client_config += f"""
DNS = {dns}
PrivateKey = {client_private_key}

[Peer]
PublicKey = {server_public_key}
PresharedKey = {psk}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = {self.server.public_ip or self.server.server_ip}:{self.server.port}
PersistentKeepalive = 25
"""

        # Write client config
        client_config_path = self.client_config_dir / f"{client_name}.conf"
        with open(client_config_path, 'w', encoding='utf-8') as f:
            f.write(client_config)

        return str(client_config_path)

    def get_server_private_key(self) -> str:
        """Get server private key from config"""
        try:
            with open('/etc/wireguard/wg0.conf', 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('PrivateKey = '):
                        return line.split(' = ')[1].strip()
        except Exception:
            pass
        return ""


class WireGuardClientManager(WireGuardBase):
    """Class for WireGuard client management operations"""

    def __init__(self):
        super().__init__()
        # Server configuration for client operations
        self.server = ServerConfig()

    def create_client_config(self, client_name: str, dns: str,
                             ipv6: Optional[str] = None) -> tuple[str, dict]:
        """Create client configuration file"""
        # Find next available IP
        octet = 2
        while True:
            if octet >= 255:
                self.print_error(
                    "253 clients are already configured. The WireGuard internal subnet is full!")
                sys.exit(1)

            # Check if IP is already used
            if not self.is_ip_used(f"10.7.0.{octet}"):
                break
            octet += 1

        # Generate client keys
        client_private_key, client_public_key = self.generate_wireguard_keys()
        psk = self.run_command(
            ["wg", "genpsk"], capture_output=True).stdout.strip()

        # Add client to server config
        server_config = f"""
# BEGIN_PEER {client_name}
[Peer]
PublicKey = {client_public_key}
PresharedKey = {psk}
AllowedIPs = 10.7.0.{octet}/32"""

        if ipv6:
            server_config += f", fddd:2c4:2c4:2c4::{octet}/128"

        server_config += f"""
# END_PEER {client_name}
"""

        # Append to server config
        with open('/etc/wireguard/wg0.conf', 'a', encoding='utf-8') as f:
            f.write(server_config)

        # Get server info from config
        endpoint_info = self.get_server_endpoint_info()

        # Create client config
        client_config = f"""[Interface]
Address = 10.7.0.{octet}/24"""

        if ipv6:
            client_config += f"\nAddress = fddd:2c4:2c4:2c4::{octet}/64"

        # Get server public key
        server_private_key = self.get_server_private_key()
        server_public_key = self.run_command(
            ["wg", "pubkey"], input_text=server_private_key, capture_output=True).stdout.strip()

        client_config += f"""
DNS = {dns}
PrivateKey = {client_private_key}

[Peer]
PublicKey = {server_public_key}
PresharedKey = {psk}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = {endpoint_info['endpoint']}:{endpoint_info['port']}
PersistentKeepalive = 25
"""

        # Write client config
        client_config_path = self.client_config_dir / f"{client_name}.conf"
        with open(client_config_path, 'w', encoding='utf-8') as f:
            f.write(client_config)

        # Return both path and client info for peer configuration
        client_info = {
            'public_key': client_public_key,
            'psk': psk,
            'octet': octet
        }

        return str(client_config_path), client_info

    def is_ip_used(self, ip: str) -> bool:
        """Check if IP address is already used by a client"""
        try:
            with open('/etc/wireguard/wg0.conf', 'r', encoding='utf-8') as f:
                content = f.read()
                return f"AllowedIPs = {ip}/" in content
        except Exception:
            return False

    def get_server_private_key(self) -> str:
        """Get server private key from config"""
        try:
            with open('/etc/wireguard/wg0.conf', 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('PrivateKey = '):
                        return line.split(' = ')[1].strip()
        except Exception:
            pass
        return ""

    def get_server_endpoint_info(self) -> dict:
        """Get server endpoint information from config"""
        endpoint_info = {'endpoint': '127.0.0.1', 'port': '51820'}
        try:
            with open('/etc/wireguard/wg0.conf', 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('# ENDPOINT '):
                        endpoint_info['endpoint'] = line.split(' ')[2].strip()
                    elif line.startswith('ListenPort = '):
                        endpoint_info['port'] = line.split(' = ')[1].strip()
        except Exception:
            pass
        return endpoint_info

    def manage_existing_installation(self):
        """Manage existing WireGuard installation"""
        if not self.wg_config_path.exists():
            self.print_error("WireGuard is not installed.")
            return

        self.print_banner("WireGuard Management")

        while True:
            print("\nSelect an option:")
            print("   1) Add a new client")
            print("   2) Remove an existing client")
            print("   3) Remove WireGuard")
            print("   4) Exit")

            try:
                choice = input("Option: ").strip()

                if choice == "1":
                    self.add_client()
                elif choice == "2":
                    self.remove_client()
                elif choice == "3":
                    # Use installer for removal
                    installer = WireGuardInstaller()
                    installer.remove_wireguard()
                    break
                elif choice == "4":
                    break
                else:
                    print(f"{choice}: invalid selection.")
            except KeyboardInterrupt:
                break

    def add_client(self):
        """Add a new client"""
        print("\nProvide a name for the client:")

        while True:
            try:
                client_name = input("Name: ").strip()
                if not client_name:
                    continue

                # Sanitize client name
                client_name = re.sub(r'[^0-9a-zA-Z_-]', '_', client_name)[:15]

                # Check if name already exists
                if self.client_exists(client_name):
                    print(f"{client_name}: name already exists.")
                    continue

                break
            except KeyboardInterrupt:
                return

        # Get DNS preference
        dns = self.select_dns()

        # Create client
        client_config_path, client_info = self.create_client_config(
            client_name, dns, self.server.server_ipv6)

        # Reload WireGuard configuration
        try:
            # Extract only the peer configuration for the new client
            peer_config = f"""[Peer]
PublicKey = {client_info['public_key']}
PresharedKey = {client_info['psk']}
AllowedIPs = 10.7.0.{client_info['octet']}/32"""
            if self.server.server_ipv6:
                peer_config += f", fddd:2c4:2c4:2c4::{client_info['octet']}/128"

            # Write peer config to temporary file and use wg addconf
            with tempfile.NamedTemporaryFile(mode='w', suffix='.conf',
                                             delete=False) as temp_file:
                temp_file.write(peer_config)
                temp_file.flush()
                self.run_command(["wg", "addconf", "wg0", temp_file.name])
                os.unlink(temp_file.name)
        except (subprocess.CalledProcessError, OSError, FileNotFoundError):
            self.run_command(["systemctl", "reload", "wg-quick@wg0.service"])

        # Generate QR code
        self.generate_qr_code(client_config_path)

        print(
            f"\n{client_name} added. Configuration available in: {client_config_path}")

    def client_exists(self, client_name: str) -> bool:
        """Check if client already exists"""
        try:
            with open('/etc/wireguard/wg0.conf', 'r', encoding='utf-8') as f:
                content = f.read()
                return f"# BEGIN_PEER {client_name}" in content
        except Exception:
            return False

    def remove_client(self):
        """Remove an existing client"""
        # Get list of clients
        clients = self.get_client_list()

        if not clients:
            print("\nThere are no existing clients!")
            return

        print("\nSelect the client to remove:")
        for i, client in enumerate(clients, 1):
            print(f"   {i}) {client}")

        while True:
            try:
                choice = input("Client: ").strip()
                choice_num = int(choice)

                if 1 <= choice_num <= len(clients):
                    client_name = clients[choice_num - 1]
                    break
                else:
                    print(f"{choice}: invalid selection.")
            except (ValueError, KeyboardInterrupt):
                return

        # Confirm removal
        while True:
            try:
                confirm = input(
                    f"Confirm {client_name} removal? [y/N]: ").strip().lower()
                if confirm in ['y', 'yes']:
                    break
                elif confirm in ['n', 'no', '']:
                    return
                else:
                    print("Invalid input.")
            except KeyboardInterrupt:
                return

        # Remove client
        self.remove_client_from_config(client_name)

        print(f"\n{client_name} removed!")

    def get_client_list(self) -> List[str]:
        """Get list of existing clients"""
        clients = []
        try:
            with open('/etc/wireguard/wg0.conf', 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('# BEGIN_PEER '):
                        client_name = line.split(' ')[-1].strip()
                        clients.append(client_name)
        except Exception:
            pass
        return clients

    def remove_client_from_config(self, client_name: str):
        """Remove client from WireGuard configuration"""
        try:
            # Read current config
            with open('/etc/wireguard/wg0.conf', 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Find and remove client section
            new_lines = []
            skip_section = False

            for line in lines:
                if f"# BEGIN_PEER {client_name}" in line:
                    skip_section = True
                    continue
                elif f"# END_PEER {client_name}" in line:
                    skip_section = False
                    continue
                elif not skip_section:
                    new_lines.append(line)

            # Write updated config
            with open('/etc/wireguard/wg0.conf', 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

            # Reload configuration
            self.run_command(["systemctl", "reload", "wg-quick@wg0.service"])

        except FileNotFoundError:
            self.print_error("WireGuard configuration file not found")
        except PermissionError:
            self.print_error(
                "Permission denied: Cannot modify WireGuard configuration")
        except (OSError, IOError) as e:
            self.print_error(f"File operation failed: {e}")
        except subprocess.CalledProcessError as e:
            self.print_error(f"Failed to reload WireGuard service: {e}")
        except Exception as e:
            self.print_error(f"Unexpected error removing client: {e}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="WireGuard VPN Installer")
    parser.add_argument("--install", action="store_true",
                        help="Install WireGuard")
    parser.add_argument("--manage", action="store_true",
                        help="Manage existing installation")

    args = parser.parse_args()

    if args.install:
        installer = WireGuardInstaller()
        installer.install_wireguard()
    elif args.manage:
        client_manager = WireGuardClientManager()
        client_manager.manage_existing_installation()
    else:
        # Interactive mode
        installer = WireGuardInstaller()
        if installer.wg_config_path.exists():
            client_manager = WireGuardClientManager()
            client_manager.manage_existing_installation()
        else:
            installer.install_wireguard()


if __name__ == "__main__":
    main()
