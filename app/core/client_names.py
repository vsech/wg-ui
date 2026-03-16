"""
Shared client name validation helpers for API and CLI flows.
"""
from __future__ import annotations

import re

CLIENT_NAME_MAX_LENGTH = 15
CLIENT_NAME_ALLOWED_DESCRIPTION = "letters, digits, underscores and hyphens"
CLIENT_NAME_PATTERN = re.compile(
    rf"^[0-9A-Za-z_-]{{1,{CLIENT_NAME_MAX_LENGTH}}}$"
)


def sanitize_client_name(value: str) -> str:
    """Return the legacy CLI-safe representation of a client name."""
    normalized = (value or "").strip()
    normalized = re.sub(r"[^0-9A-Za-z_-]", "_", normalized)
    return normalized[:CLIENT_NAME_MAX_LENGTH]


def validate_client_name(value: str) -> str:
    """Validate the shared client naming contract."""
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError("Client name must not be empty")
    if not CLIENT_NAME_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Client name must be 1-15 chars and contain only "
            f"{CLIENT_NAME_ALLOWED_DESCRIPTION}"
        )
    return normalized
