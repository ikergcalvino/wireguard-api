# wireguard-api

WireGuard VPN dockerizado con API REST (FastAPI) para gestionar interfaces y peers.

## Estructura

```
wireguard-api/
├── api/
│   ├── main.py            # FastAPI app + auth middleware
│   ├── config.py          # Settings via env vars
│   ├── models/
│   │   ├── interfaces.py  # Schemas de interfaces
│   │   └── peers.py       # Schemas de peers
│   ├── routers/
│   │   ├── interfaces.py  # CRUD de interfaces
│   │   └── peers.py       # CRUD de peers (sub-recurso)
│   └── services/
│       └── wireguard.py   # Gestión de WireGuard (wg CLI)
├── Dockerfile             # Alpine + wireguard-tools + Python
├── docker-compose.yml
├── entrypoint.sh          # Levanta interfaces existentes + arranca API
├── requirements.txt
├── .env.example
└── config/                # Volumen persistente (generado)
```

## Inicio rápido

```bash
cp .env.example .env
# Edita .env con tu configuración (endpoint, API key, etc.)
docker compose up -d --build
```

## API Endpoints

Todos los endpoints están bajo `/api/v1`. Si `WG_API_API_KEY` está configurada, incluye el header `X-API-Key`.

### Interfaces

| Método   | Ruta                          | Descripción                    |
|----------|-------------------------------|--------------------------------|
| `GET`    | `/`                           | Info de la API                 |
| `GET`    | `/api/v1/health`              | Health check                   |
| `GET`    | `/api/v1/interfaces`          | Listar interfaces              |
| `POST`   | `/api/v1/interfaces`          | Crear interfaz                 |
| `GET`    | `/api/v1/interfaces/{name}`   | Detalle de una interfaz        |
| `DELETE` | `/api/v1/interfaces/{name}`   | Eliminar interfaz              |

### Peers

| Método   | Ruta                                          | Descripción            |
|----------|-----------------------------------------------|------------------------|
| `GET`    | `/api/v1/interfaces/{iface}/peers`            | Listar peers           |
| `POST`   | `/api/v1/interfaces/{iface}/peers`            | Crear peer             |
| `GET`    | `/api/v1/interfaces/{iface}/peers/{public_key}`  | Detalle de un peer     |
| `DELETE` | `/api/v1/interfaces/{iface}/peers/{public_key}`  | Eliminar peer          |

Los peers se identifican por su `public_key`. Al crear un peer se devuelve la `private_key` **una sola vez** (el servidor no la persiste).

### Ejemplos

```bash
# Crear interfaz
curl -X POST http://localhost:8000/api/v1/interfaces \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key" \
  -d '{"name": "wg0", "address": "10.0.0.1/24", "listen_port": 51820}'

# Crear peer en wg0 (devuelve private_key una sola vez)
curl -X POST http://localhost:8000/api/v1/interfaces/wg0/peers \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key" \
  -d '{}'
```

## Configuración (variables de entorno)

| Variable                     | Default            | Descripción                        |
|------------------------------|--------------------|------------------------------------|
| `WG_API_WG_CONFIG_DIR`      | `/etc/wireguard`   | Directorio de configuración        |
| `WG_API_WG_SERVER_ENDPOINT` | (vacío)            | IP/dominio público del servidor    |
| `WG_API_API_KEY`            | (vacío)            | API Key (si vacío, sin auth)       |