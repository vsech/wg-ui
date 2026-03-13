# WireGuard UI API

FastAPI backend предоставляет API под префиксом `/api`.

## Аутентификация

JWT-токен передаётся в заголовке:

```text
Authorization: Bearer <token>
```

## Эндпоинты

### Login

```http
POST /api/auth/login
Content-Type: application/json
```

```json
{
  "username": "admin",
  "password": "secret"
}
```

Ответ:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

### Register

Требует уже валидный JWT.

```http
POST /api/auth/register
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "username": "operator",
  "password": "strong-password"
}
```

### List Clients

```http
GET /api/clients/
Authorization: Bearer <token>
```

Пример ответа:

```json
[
  {
    "id": 1,
    "name": "phone",
    "ip_address": "10.7.0.2",
    "created_at": "2026-03-13T07:11:13.563299",
    "is_active": true,
    "last_handshake": "2026-03-13T06:58:12.000000",
    "bytes_received": 271349,
    "bytes_sent": 587182
  }
]
```

### Create Client

```http
POST /api/clients/
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "name": "laptop",
  "dns": "1.1.1.1, 1.0.0.1"
}
```

Ответ содержит готовый текст конфига и QR:

```json
{
  "name": "laptop",
  "config": "[Interface]\n...",
  "qr_code": "data:image/png;base64,...",
  "last_handshake": null,
  "bytes_received": 0,
  "bytes_sent": 0
}
```

### Delete Client

```http
DELETE /api/clients/{client_name}
Authorization: Bearer <token>
```

Ответ:

```json
{
  "message": "Client laptop deleted successfully"
}
```

### Get Client Config

```http
GET /api/clients/{client_name}/config
Authorization: Bearer <token>
```

Возвращает:
- текст клиентского `.conf`
- QR code
- кешированные runtime-метрики

Важно: endpoint требует наличия файла `/opt/wg-ui/data/{client_name}.conf`. Если этот файл утерян, API вернёт `404`, даже если peer всё ещё существует в `wg0.conf`.

### Get Client QR

```http
GET /api/clients/{client_name}/qr
Authorization: Bearer <token>
```

Важно: как и `/config`, этот endpoint зависит от существующего клиентского `.conf`.

## Формат ошибок

Typed exceptions рендерятся в единый JSON:

```json
{
  "detail": "Client not found",
  "code": "not_found",
  "details": {}
}
```

Типовые статусы:
- `401` для ошибок аутентификации
- `404` для отсутствующих клиентов или client config files
- `409` для конфликтов, например при создании клиента с существующим именем
- `500` для необработанных инфраструктурных сбоев

## cURL примеры

```bash
TOKEN=$(curl -s -X POST "http://127.0.0.1:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"secret"}' | jq -r '.access_token')

curl -s "http://127.0.0.1:8000/api/clients/" \
  -H "Authorization: Bearer $TOKEN"

curl -s "http://127.0.0.1:8000/api/clients/laptop/config" \
  -H "Authorization: Bearer $TOKEN"
```

## Operational notes

- `/api/clients/` синхронизирует кеш в SQLite с реальными peers из WireGuard config
- runtime-статистика читается через `wg show`
- source of truth для peers: `/etc/wireguard/wg0.conf`
- source of truth для downloadable client configs: `/opt/wg-ui/data/*.conf`
