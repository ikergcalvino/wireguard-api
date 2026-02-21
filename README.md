# wireguard-api

REST API to manage [WireGuard](https://www.wireguard.com/) interfaces and peers on the host, built with [FastAPI](https://fastapi.tiangolo.com/).

The API runs inside a Docker container with `network_mode: host`, giving it direct access to the host's network stack. It wraps `wg` and `wg-quick` commands using safe subprocess execution (no shell interpolation) to prevent command injection.

## Features

- **CRUD for interfaces** — create, inspect, delete WireGuard interfaces
- **CRUD for peers** — add, update, remove, and list peers on any interface
- **Lifecycle actions** — bring interfaces up/down and persist runtime changes
- **Input validation** — interface names and WireGuard keys are validated with Pydantic
- **Command injection safe** — all subprocess calls use `exec` with argument lists, never shell
- **Optional API Key auth** — protect endpoints with `X-API-Key` header
- **CORS support** — configurable origins for frontend integration
- **Structured logging** — timestamped, leveled logs configurable via environment
- **Minimal Docker image** — single-stage `python:3.13-alpine`

## Prerequisites

The **host** machine must have:

- WireGuard kernel module loaded (`sudo modprobe wireguard`)
- IP forwarding enabled (`sysctl net.ipv4.ip_forward=1`)
- `/etc/wireguard` directory with appropriate permissions
- Docker and Docker Compose

## Quick Start

```bash
git clone https://github.com/your-user/wireguard-api.git
cd wireguard-api
cp .env.example .env    # edit with your settings
docker compose up -d --build
```

The API will be available at `http://localhost:8000` (or your configured `WG_API_PORT`).

## API Reference

All endpoints are under `/api/v1`. If `WG_API_KEY` is set, include `X-API-Key: <key>` in request headers.

Interactive docs: `/docs` (Swagger UI) and `/redoc` (ReDoc).

### Interfaces

| Method   | Path                             | Description                  |
|----------|----------------------------------|------------------------------|
| `GET`    | `/api/v1/interfaces`             | List active interfaces       |
| `POST`   | `/api/v1/interfaces`             | Create interface (.conf + up)|
| `GET`    | `/api/v1/interfaces/{name}`      | Get interface details        |
| `DELETE` | `/api/v1/interfaces/{name}`      | Delete interface (down + rm) |
| `POST`   | `/api/v1/interfaces/{name}/up`   | Bring interface up           |
| `POST`   | `/api/v1/interfaces/{name}/down` | Bring interface down         |
| `POST`   | `/api/v1/interfaces/{name}/save` | Persist runtime to .conf     |

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

```bash
# Create an interface
curl -X POST http://localhost:8000/api/v1/interfaces \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key" \
  -d '{
    "name": "wg0",
    "address": "10.0.0.1/24",
    "listen_port": 51820,
    "private_key": "<server-private-key>"
  }'

# Add a peer
curl -X POST http://localhost:8000/api/v1/interfaces/wg0/peers \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key" \
  -d '{
    "public_key": "<peer-public-key>",
    "allowed_ips": "10.0.0.2/32"
  }'

# Save runtime state to .conf
curl -X POST http://localhost:8000/api/v1/interfaces/wg0/save \
  -H "X-API-Key: your-secret-api-key"
```

## Configuration

| Variable          | Default            | Description                                  |
|-------------------|--------------------|----------------------------------------------|
| `WG_API_KEY`      | (empty)            | API key for auth; if empty, auth is disabled  |
| `WG_API_PORT`     | `8000`             | API server port                              |
| `WG_LOG_LEVEL`    | `INFO`             | Log level: DEBUG, INFO, WARNING, ERROR       |
| `WG_CORS_ORIGINS` | `*`                | Comma-separated allowed CORS origins         |
| `WG_CONFIG_DIR`   | `/etc/wireguard`   | Path to WireGuard configuration directory    |

## Project Structure

```
wireguard-api/
├── api/
│   ├── config.py          # Centralized settings (pydantic-settings)
│   ├── exceptions.py      # Global exception handlers
│   ├── main.py            # FastAPI app, middleware, auth
│   ├── models/
│   │   ├── interfaces.py  # Interface Pydantic model
│   │   └── peers.py       # Peer Pydantic model
│   ├── routers/
│   │   ├── interfaces.py  # Interface endpoints
│   │   └── peers.py       # Peer endpoints
│   └── services/
│       └── wireguard.py   # wg/wg-quick subprocess wrappers
├── tests/                 # pytest test suite
├── .github/               # CI workflow, issue & PR templates
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml         # Project metadata, ruff & pytest config
├── Makefile               # Dev shortcuts
└── requirements.txt
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e ".[dev]"
cp .env.example .env
```

```bash
make dev       # run with hot reload
make lint      # ruff check
make format    # ruff format
make test      # pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines.

## How It Works

The API is stateless. It delegates everything to WireGuard's own tooling:

- **Interfaces** are managed via `wg-quick up/down/save` and `wg show`
- **Peers** are managed via `wg set` and inspected via `wg show dump`
- The `.conf` files in `/etc/wireguard` are the source of truth at startup
- The kernel WireGuard interface is the source of truth at runtime

The Docker container runs with `network_mode: host` and `NET_ADMIN` capability, allowing it to manage the host's WireGuard interfaces directly without running WireGuard inside the container.

## Security

- All subprocess calls use `create_subprocess_exec` with argument lists (no shell injection)
- Interface names validated against `^[a-zA-Z0-9_-]{1,15}$`
- WireGuard keys validated as proper base64-encoded 32-byte keys
- Preshared keys passed via stdin to avoid process list exposure
- Container requires only `NET_ADMIN` capability

## License

[MIT](LICENSE)