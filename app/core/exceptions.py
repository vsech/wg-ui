"""
Typed application exceptions.
"""
from __future__ import annotations


class AppError(Exception):
    """Base application exception."""

    status_code = 400
    code = "application_error"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_error"


class AuthorizationError(AppError):
    status_code = 403
    code = "authorization_error"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class IntegrationError(AppError):
    status_code = 502
    code = "integration_error"


class ConfigurationError(AppError):
    status_code = 500
    code = "configuration_error"
