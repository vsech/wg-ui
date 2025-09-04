# WireGuard Client Manager - Project Structure

This document describes the refactored project structure following DRY and KISS principles.

## Directory Structure

```
wg-ui/
├── app/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # Application configuration
│   │   ├── database.py        # Database setup and session management
│   │   ├── dependencies.py    # FastAPI dependencies
│   │   └── security.py        # Authentication and security utilities
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py        # SQLAlchemy database models
│   │   └── schemas.py         # Pydantic request/response schemas
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py           # Authentication endpoints
│   │   └── clients.py        # Client management endpoints
│   └── services/
│       ├── __init__.py
│       ├── auth.py           # Authentication business logic
│       ├── qr_generator.py   # QR code generation service
│       └── wireguard.py      # WireGuard client management service
├── main.py                   # FastAPI application entry point
├── start.py                  # Development server startup script
├── wg_installer.py          # Original WireGuard installer (unchanged)
├── requirements.txt         # Python dependencies
├── README_API.md           # API documentation
└── PROJECT_STRUCTURE.md    # This file
```

## Module Responsibilities

### Core Modules (`app/core/`)

- **config.py**: Centralized configuration management using environment variables
- **database.py**: Database engine, session factory, and connection management
- **security.py**: JWT token handling, password hashing, and verification
- **dependencies.py**: FastAPI dependency injection functions

### Models (`app/models/`)

- **database.py**: SQLAlchemy ORM models for database tables
- **schemas.py**: Pydantic models for API request/response validation

### Services (`app/services/`)

- **auth.py**: Authentication business logic (login, registration, token creation)
- **wireguard.py**: WireGuard client management operations
- **qr_generator.py**: QR code generation utilities

### Routers (`app/routers/`)

- **auth.py**: Authentication API endpoints (`/auth/login`, `/auth/register`)
- **clients.py**: Client management API endpoints (`/clients/*`)

## Key Design Principles Applied

### DRY (Don't Repeat Yourself)

1. **Centralized Configuration**: All settings in `app/core/config.py`
2. **Reusable Services**: Business logic separated into service classes
3. **Common Dependencies**: Shared dependencies in `app/core/dependencies.py`
4. **Unified Error Handling**: Consistent error responses across endpoints

### KISS (Keep It Simple, Stupid)

1. **Single Responsibility**: Each module has one clear purpose
2. **Simple Imports**: Clear module hierarchy with minimal circular dependencies
3. **Straightforward API**: RESTful endpoints with predictable behavior
4. **Minimal Abstraction**: Only necessary abstractions, avoiding over-engineering

## Usage

### Development Server

```bash
python start.py
# or
python main.py
# or
uvicorn main:app --reload
```

### Production Server

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Benefits of This Structure

1. **Maintainability**: Clear separation of concerns makes code easier to maintain
2. **Testability**: Services can be easily unit tested in isolation
3. **Scalability**: New features can be added without affecting existing code
4. **Reusability**: Services and utilities can be reused across different endpoints
5. **Configuration Management**: Environment-based configuration for different deployments
6. **Type Safety**: Pydantic schemas provide runtime type validation

## Migration from Monolithic Structure

The original `main.py` file contained:

- Database models → Moved to `app/models/database.py`
- Pydantic schemas → Moved to `app/models/schemas.py`
- Authentication logic → Moved to `app/services/auth.py`
- WireGuard operations → Moved to `app/services/wireguard.py`
- API endpoints → Moved to `app/routers/auth.py` and `app/routers/clients.py`
- Configuration → Moved to `app/core/config.py`
- Security utilities → Moved to `app/core/security.py`

The new `main.py` is now clean and focused only on application setup and routing.
