# wireguard-api

Dockerized [WireGuard](https://www.wireguard.com/) VPN server with a REST API built on [FastAPI](https://fastapi.tiangolo.com/). Manage WireGuard interfaces and peers programmatically through simple HTTP calls.

The API wraps `wg` and `wg-quick` commands, validating all inputs to prevent shell injection. It's designed to be lightweight and minimal — a single Alpine-based container running both WireGuard and the API.

## Features

- **CRUD for interfaces** — create, inspect, delete WireGuard interfaces via API
- **CRUD for peers** — add, update, remove, and list peers on any interface
- **Lifecycle actions** — bring interfaces up/down and persist runtime changes with save
- **Input validation** — interface names and WireGuard keys are validated before executing any command
- **Optional API Key auth** — protect endpoints with a simple `X-API-Key` header
- **Minimal Docker image** — multi-stage build on `python:3.13-alpine`

## Quick Start

```bash
git clone https://github.com/your-user/wireguard-api.git
cd wireguard-api
cp .env.example .env    # edit with your API key if desired
docker compose up -d --build
```

The API will be available at `http://localhost:8000`. WireGuard listens on UDP port `51820`.

Any `.conf` files present in the `./config` volume will be automatically brought up on container start.

## API Reference

All endpoints are under `/api/v1`. If `WG_API_KEY` is set, include `X-API-Key: <key>` in your request headers.

Interactive docs are available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

### Interfaces

| Method   | Path                             | Description                 |
|----------|----------------------------------|-----------------------------|
| `GET`    | `/api/v1/interfaces`             | List active interfaces      |
| `POST`   | `/api/v1/interfaces`             | Create interface (.conf + up)|
| `GET`    | `/api/v1/interfaces/{name}`      | Get interface details       |
| `DELETE` | `/api/v1/interfaces/{name}`      | Delete interface (down + rm)|
| `POST`   | `/api/v1/interfaces/{name}/up`   | Bring interface up          |
| `POST`   | `/api/v1/interfaces/{name}/down` | Bring interface down        |
| `POST`   | `/api/v1/interfaces/{name}/save` | Persist runtime to .conf    |

### Peers

| Method   | Path                                             | Description    |
|----------|--------------------------------------------------|----------------|
| `GET`    | `/api/v1/interfaces/{iface}/peers`               | List peers     |
| `POST`   | `/api/v1/interfaces/{iface}/peers`               | Add peer       |
| `GET`    | `/api/v1/interfaces/{iface}/peers/{public_key}`  | Get peer       |
| `PUT`    | `/api/v1/interfaces/{iface}/peers/{public_key}`  | Update peer    |
| `DELETE` | `/api/v1/interfaces/{iface}/peers/{public_key}`  | Remove peer    |

### Other

| Method | Path             | Description  |
|--------|------------------|--------------|
| `GET`  | `/`              | API info     |
| `GET`  | `/api/v1/health` | Health check |

## Examples

### Create an interface

```bash
curl -X POST http://localhost:8000/api/v1/interfaces \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key" \
  -d '{
    "name": "wg0",
    "address": "10.0.0.1/24",
    "listen_port": 51820,
    "private_key": "<server-private-key>"
  }'
```

### Add a peer

```bash
curl -X POST http://localhost:8000/api/v1/interfaces/wg0/peers \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key" \
  -d '{
    "public_key": "<peer-public-key>",
    "allowed_ips": "10.0.0.2/32"
  }'
```

### Update a peer

```bash
curl -X PUT http://localhost:8000/api/v1/interfaces/wg0/peers/<peer-public-key> \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key" \
  -d '{
    "public_key": "<peer-public-key>",
    "allowed_ips": "10.0.0.2/32,10.0.1.0/24"
  }'
```

### Save runtime state

```bash
curl -X POST http://localhost:8000/api/v1/interfaces/wg0/save \
  -H "X-API-Key: your-secret-api-key"
```

### Remove a peer

```bash
curl -X DELETE http://localhost:8000/api/v1/interfaces/wg0/peers/<peer-public-key> \
  -H "X-API-Key: your-secret-api-key"
```

## Configuration

| Variable     | Default | Description                             |
|--------------|---------|-----------------------------------------|
| `WG_API_KEY` | (empty) | API key for auth. If empty, auth is off |

## Project Structure

```
wireguard-api/
├── api/
│   ├── main.py            # FastAPI app + API Key auth
│   ├── models/
│   │   ├── interfaces.py  # Interface model
│   │   └── peers.py       # Peer model
│   ├── routers/
│   │   ├── interfaces.py  # CRUD + up/down/save
│   │   └── peers.py       # CRUD peers
│   └── services/
│       └── wireguard.py   # wg/wg-quick wrappers + input validation
├── Dockerfile             # Multi-stage build, python:3.13-alpine
├── docker-compose.yml
├── entrypoint.sh          # Auto-up existing interfaces + start API
└── requirements.txt
```

## How It Works

The API doesn't maintain its own state. It delegates everything to WireGuard's own tooling:

- **Interfaces** are managed via `wg-quick up/down/save` and `wg show`
- **Peers** are added/removed at runtime via `wg set` and inspected via `wg show dump`
- `POST .../save` calls `wg-quick save` to persist the current runtime state back to the `.conf` file

This means the `.conf` file in `/etc/wireguard` is the source of truth for startup, and the kernel WireGuard interface is the source of truth at runtime.

## Security

- All interface names are validated against `^[a-zA-Z0-9_-]{1,15}$`
- All WireGuard keys are validated as proper base64-encoded 32-byte keys
- The `preshared_key` is passed via stdin to avoid leaking it in the process list
- The container requires `NET_ADMIN` and `SYS_MODULE` capabilities

## License

MIT