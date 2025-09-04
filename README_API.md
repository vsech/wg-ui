# WireGuard Client Manager API

FastAPI backend for managing WireGuard VPN clients with JWT authentication and SQLite database.

## Features

- JWT-based authentication
- RESTful API for WireGuard client management
- SQLite database for user and client data
- QR code generation for client configurations
- Integration with existing WireGuardClientManager class

## Installation

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Ensure WireGuard is installed and configured:

```bash
# The wg_installer.py script should be run first to set up WireGuard
sudo python3 wg_installer.py --install
```

3. Start the API server:

```bash
python3 main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### Authentication

#### Register User

```http
POST /auth/register
Content-Type: application/json

{
    "username": "admin",
    "password": "secure_password"
}
```

#### Login

```http
POST /auth/login
Content-Type: application/json

{
    "username": "admin",
    "password": "secure_password"
}
```

Response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Client Management

All client endpoints require authentication. Include the JWT token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

#### Get All Clients

```http
GET /clients
Authorization: Bearer <token>
```

Response:

```json
[
  {
    "id": 1,
    "name": "client1",
    "ip_address": "10.7.0.2",
    "created_at": "2024-01-01T12:00:00",
    "is_active": true
  }
]
```

#### Create New Client

```http
POST /clients
Authorization: Bearer <token>
Content-Type: application/json

{
    "name": "client2",
    "dns": "8.8.8.8, 8.8.4.4"
}
```

Response:

```json
{
  "name": "client2",
  "config": "[Interface]\nAddress = 10.7.0.3/24\nDNS = 8.8.8.8, 8.8.4.4\nPrivateKey = ...\n\n[Peer]\n...",
  "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
}
```

#### Delete Client

```http
DELETE /clients/{client_name}
Authorization: Bearer <token>
```

Response:

```json
{
  "message": "Client client2 deleted successfully"
}
```

#### Generate QR Code for Existing Client

```http
GET /clients/{client_name}/qr
Authorization: Bearer <token>
```

Response:

```json
{
  "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
}
```

## Usage Examples

### Python Client Example

```python
import requests
import json

# API base URL
BASE_URL = "http://localhost:8000"

# Login and get token
def login(username, password):
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "username": username,
        "password": password
    })
    return response.json()["access_token"]

# Create headers with token
def get_headers(token):
    return {"Authorization": f"Bearer {token}"}

# Example usage
token = login("admin", "admin123")
headers = get_headers(token)

# Get all clients
clients = requests.get(f"{BASE_URL}/clients", headers=headers).json()
print("Current clients:", clients)

# Create new client
new_client = requests.post(f"{BASE_URL}/clients",
    headers=headers,
    json={"name": "mobile_device", "dns": "1.1.1.1, 1.0.0.1"}
).json()
print("New client config:", new_client["config"])

# Get QR code for client
qr_response = requests.get(f"{BASE_URL}/clients/mobile_device/qr", headers=headers).json()
print("QR code data URL:", qr_response["qr_code"][:50] + "...")

# Delete client
delete_response = requests.delete(f"{BASE_URL}/clients/mobile_device", headers=headers).json()
print("Delete result:", delete_response["message"])
```

### cURL Examples

```bash
# Login
TOKEN=$(curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' | jq -r '.access_token')

# Get clients
curl -X GET "http://localhost:8000/clients" \
  -H "Authorization: Bearer $TOKEN"

# Create client
curl -X POST "http://localhost:8000/clients" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "laptop", "dns": "8.8.8.8, 8.8.4.4"}'

# Delete client
curl -X DELETE "http://localhost:8000/clients/laptop" \
  -H "Authorization: Bearer $TOKEN"

# Get QR code
curl -X GET "http://localhost:8000/clients/laptop/qr" \
  -H "Authorization: Bearer $TOKEN"
```

## Configuration

### Environment Variables

- `SECRET_KEY`: JWT secret key (default: "your-secret-key-change-this-in-production")
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration time in minutes (default: 30)
- `DATABASE_URL`: SQLite database URL (default: "sqlite:///./wireguard.db")

### Production Setup

1. Set a secure SECRET_KEY:

```bash
export SECRET_KEY="your-very-secure-secret-key-here"
```

2. Configure CORS origins in `main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Replace with your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

3. Use a production WSGI server:

```bash
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Database Schema

### Users Table

- `id`: Primary key
- `username`: Unique username
- `hashed_password`: Bcrypt hashed password
- `is_active`: Boolean flag
- `created_at`: Timestamp

### Clients Table

- `id`: Primary key
- `name`: Unique client name
- `public_key`: WireGuard public key
- `ip_address`: Assigned IP address
- `created_at`: Timestamp
- `is_active`: Boolean flag

## Security Considerations

1. **Change the default SECRET_KEY** in production
2. **Use HTTPS** in production
3. **Configure CORS** properly for your domain
4. **Run with appropriate permissions** (the API needs access to WireGuard configuration files)
5. **Regular token rotation** - tokens expire after 30 minutes by default
6. **Database backups** - backup the SQLite database regularly

## Troubleshooting

### Common Issues

1. **Permission denied errors**: Ensure the API runs with sufficient privileges to modify WireGuard configurations
2. **WireGuard not found**: Make sure WireGuard is installed and `wg` command is available
3. **Database locked**: Ensure only one instance of the API is running
4. **Token expired**: Re-authenticate to get a new token

### Logs

The API uses FastAPI's built-in logging. For more detailed logs, run with:

```bash
uvicorn main:app --log-level debug
```

## API Documentation

Once the server is running, visit:

- Interactive API docs: http://localhost:8000/docs
- ReDoc documentation: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json
