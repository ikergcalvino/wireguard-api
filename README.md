# wireguard-api

REST API to manage [WireGuard](https://www.wireguard.com/) interfaces and peers on the host, built with [FastAPI](https://fastapi.tiangolo.com/).

The API runs inside a Docker container with `network_mode: host`, giving it direct access to the host's network stack. It wraps `wg` and `wg-quick` commands using safe subprocess execution (no shell interpolation) to prevent command injection.

## Features

- **CRUD for interfaces** — create, read, update, delete WireGuard interfaces (active and inactive)
- **CRUD for peers** — add, update, remove, and list peers on any interface (active and inactive)
- **Lifecycle actions** — bring interfaces up/down and persist runtime changes
- **Auto-save** — peer changes are automatically persisted to `.conf` files
- **Offline visibility** — interfaces and peers from `.conf` files are visible even when not running
- **Input validation** — interface names and WireGuard keys are validated with Pydantic
- **Command injection safe** — all subprocess calls use `exec` with argument lists, never shell
- **Optional API Key auth** — protect endpoints with `X-API-Key` header
- **CORS support** — configurable origins for frontend integration
- **Structured logging** — timestamped, leveled logs configurable via environment
- **Minimal Docker image** — single-stage `python:3.13-alpine`

## Prerequisites

Regardless of the installation method, the **host** must have:

- WireGuard kernel module loaded (`sudo modprobe wireguard`)
- IP forwarding enabled (`sysctl net.ipv4.ip_forward=1`)
- `/etc/wireguard` directory with appropriate permissions

## Installation

```bash
git clone https://github.com/ikergcalvino/wireguard-api.git
cd wireguard-api
cp .env.example .env    # edit with your settings
```

### Docker (recommended)

Requires Docker and Docker Compose.

```bash
make up        # or: docker compose up -d --build
make down      # stop
make logs      # follow logs
```

### Native / Bare metal

Requires Python 3.10+ and `wireguard-tools` installed on the host.

```bash
python -m venv .venv && source .venv/bin/activate
make install   # pip install .
make run       # uvicorn on 0.0.0.0:8000
```

> [!IMPORTANT]
> The process needs `CAP_NET_ADMIN` to manage WireGuard interfaces. Run with `sudo` or grant the capability to the Python binary.

The API will be available at `http://localhost:8000` (or your configured `WG_API_PORT`).

## API Reference

All endpoints are under `/api/v1`. If `WG_API_KEY` is set, include `X-API-Key: <key>` in request headers.

Interactive docs: `/docs` (Swagger UI) and `/redoc` (ReDoc).

### Interfaces

| Method   | Path                             | Description                     |
|----------|----------------------------------|---------------------------------|
| `GET`    | `/api/v1/interfaces`             | List all interfaces (up & down) |
| `POST`   | `/api/v1/interfaces`             | Create interface (.conf + up)   |
| `GET`    | `/api/v1/interfaces/{name}`      | Get interface details           |
| `PUT`    | `/api/v1/interfaces/{name}`      | Update interface config         |
| `DELETE` | `/api/v1/interfaces/{name}`      | Delete interface (down + rm)    |
| `POST`   | `/api/v1/interfaces/{name}/up`   | Bring interface up              |
| `POST`   | `/api/v1/interfaces/{name}/down` | Bring interface down            |
| `POST`   | `/api/v1/interfaces/{name}/save` | Persist runtime to .conf        |

### Peers

| Method   | Path                                            | Description |
|----------|-------------------------------------------------|-------------|
| `GET`    | `/api/v1/interfaces/{iface}/peers`              | List peers  |
| `POST`   | `/api/v1/interfaces/{iface}/peers`              | Add peer    |
| `GET`    | `/api/v1/interfaces/{iface}/peers/{public_key}` | Get peer    |
| `PUT`    | `/api/v1/interfaces/{iface}/peers/{public_key}` | Update peer |
| `DELETE` | `/api/v1/interfaces/{iface}/peers/{public_key}` | Remove peer |

> [!NOTE]
> `POST`, `PUT`, and `DELETE` peer operations automatically persist changes to the `.conf` file.
> If auto-save fails, the response includes an `X-Save-Warning` header.
>
> Interface responses include a `status` field (`"up"` or `"down"`) indicating whether the interface is currently running.

### Other

| Method | Path             | Description  |
|--------|------------------|--------------|
| `GET`  | `/api/v1`        | API info     |
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

# Save runtime state to .conf (usually automatic after peer changes)
curl -X POST http://localhost:8000/api/v1/interfaces/wg0/save \
  -H "X-API-Key: your-secret-api-key"

# List all interfaces (both running and stopped)
curl http://localhost:8000/api/v1/interfaces \
  -H "X-API-Key: your-secret-api-key"

```

## Configuration

| Variable          | Default          | Description                                                        |
|-------------------|------------------|--------------------------------------------------------------------|
| `WG_API_KEY`      | (empty)          | API key for authentication; if empty, authentication is disabled   |
| `WG_API_PORT`     | `8000`           | API server port (used by Makefile and Compose, not the app itself) |
| `WG_LOG_LEVEL`    | `INFO`           | Log level: DEBUG, INFO, WARNING, ERROR                             |
| `WG_CORS_ORIGINS` | `*`              | Comma-separated allowed CORS origins                               |
| `WG_CONFIG_DIR`   | `/etc/wireguard` | Path to WireGuard configuration directory                          |

## Project Structure

```
wireguard-api/
├── api/
│   ├── config.py          # Centralized settings (pydantic-settings)
│   ├── dependencies.py    # Shared FastAPI dependencies (API key auth)
│   ├── exceptions.py      # Global exception handlers
│   ├── logging.py         # Logging configuration (dictConfig)
│   ├── main.py            # FastAPI app, middleware, routes
│   ├── models/
│   │   ├── __init__.py    # Shared validation patterns
│   │   ├── interfaces.py  # Interface model
│   │   └── peers.py       # Peer model
│   ├── routers/
│   │   ├── __init__.py    # Shared path parameter types
│   │   ├── interfaces.py  # Interface endpoints
│   │   └── peers.py       # Peer endpoints
│   └── services/
│       ├── __init__.py    # Public service exports
│       └── wireguard.py   # wg/wg-quick subprocess wrappers
├── tests/                 # pytest test suite
├── .github/               # CI workflow, issue & PR templates
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml         # Project metadata, dependencies & tool config
└── Makefile               # Dev shortcuts
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
make install-dev   # pip install -e ".[dev]"
cp .env.example .env
```

```bash
make dev       # run with hot reload
make lint      # ruff check
make format    # ruff format
make type      # ty check
make test      # pytest
```

## How It Works

The API is stateless. It delegates everything to WireGuard's own tooling:

- **Interfaces** are managed via `wg-quick up/down/save`, `wg syncconf` (live updates), and `wg show`
- **Peers** are managed via `wg set` and inspected via `wg show dump`
- The `.conf` files in `/etc/wireguard` are the source of truth at startup
- The kernel WireGuard interface is the source of truth at runtime
- **Down interfaces** are read directly from `.conf` files, so manually added configs are visible immediately
- **Peer changes** (`POST`, `PUT`, `DELETE`) trigger an automatic `wg-quick save` to persist the change
- **Interface updates** (`PUT`) create a `.conf.bak` backup and restore it on failure

The Docker container runs with `network_mode: host` and `NET_ADMIN` capability, allowing it to manage the host's WireGuard interfaces directly without running WireGuard inside the container.

## Security

- All subprocess calls use `create_subprocess_exec` with argument lists (no shell injection)
- Interface names validated against `^[a-zA-Z0-9_=+.-]{1,15}$`
- WireGuard keys validated as proper base64-encoded 32-byte keys
- Private keys are never exposed in API responses
- Preshared keys passed via stdin to avoid process list exposure
- Config files written with `0600` permissions
- Container requires only `NET_ADMIN` capability

> [!CAUTION]
> The `PreUp`, `PostUp`, `PreDown`, and `PostDown` fields are executed by `bash` via `wg-quick`.
> An authenticated user can set arbitrary commands through these fields. In multi-tenant or untrusted environments,
> consider restricting access to the API key or disabling these fields at the application level.

## License

[MIT](LICENSE)