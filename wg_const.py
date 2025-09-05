
class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


class SystemConfig:
    """System configuration container"""

    def __init__(self):
        self.os_name = ""
        self.os_version = ""
        self.use_boringtun = False


class ServerConfig:
    """Server configuration container"""

    def __init__(self):
        self.server_ip = None
        self.server_ipv6 = None
        self.public_ip = None
        self.port = None