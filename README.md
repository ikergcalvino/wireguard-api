# wireguard-api

WireGuard VPN dockerizado con API REST (FastAPI) para gestionar peers y monitorizar el servidor.

## Estructura

```
wireguard-api/
├── api/
│   ├── main.py            # FastAPI app + auth middleware
│   ├── config.py          # Settings via env vars
│   ├── models/
│   │   └── peers.py       # Pydantic schemas
│   ├── routers/
│   │   ├── peers.py       # CRUD de peers
│   │   └── server.py      # Estado del servidor
│   └── services/
│       └── wireguard.py   # Gestión de WireGuard (wg CLI)
├── Dockerfile             # Alpine + wireguard-tools + Python
├── docker-compose.yml
├── entrypoint.sh          # Inicializa WireGuard + arranca API
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

| Método   | Ruta                    | Descripción                  |
|----------|-------------------------|------------------------------|
| `GET`    | `/`                     | Info de la API               |
| `GET`    | `/api/v1/server/health` | Health check                 |
| `GET`    | `/api/v1/server/status` | Estado de WireGuard          |
| `GET`    | `/api/v1/peers`         | Listar todos los peers       |
| `GET`    | `/api/v1/peers/{name}`  | Obtener un peer por nombre   |
| `POST`   | `/api/v1/peers`         | Crear un nuevo peer          |
| `DELETE` | `/api/v1/peers/{name}`  | Eliminar un peer             |

### Crear peer

```bash
curl -X POST http://localhost:8000/api/v1/peers \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key" \
  -d '{"name": "mi-laptop", "dns": "1.1.1.1"}'
```

## Configuración (variables de entorno)

| Variable                     | Default            | Descripción                        |
|------------------------------|--------------------|------------------------------------|
| `WG_API_WG_INTERFACE`       | `wg0`              | Interfaz WireGuard                 |
| `WG_API_WG_CONFIG_DIR`      | `/etc/wireguard`   | Directorio de configuración        |
| `WG_API_WG_SERVER_IP`       | `10.0.0.1`         | IP del servidor en la VPN          |
| `WG_API_WG_SUBNET`          | `10.0.0.0/24`      | Subred de la VPN                   |
| `WG_API_WG_PORT`            | `51820`            | Puerto UDP de WireGuard            |
| `WG_API_WG_SERVER_ENDPOINT` | (vacío)            | IP/dominio público del servidor    |
| `WG_API_API_KEY`            | (vacío)            | API Key (si vacío, sin auth)       |