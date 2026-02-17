# wireguard-api

Microservicio mínimo: WireGuard dockerizado con API REST que actúa como wrapper sobre `wg` y `wg-quick`. No manipula ficheros `.conf` directamente — solo ejecuta comandos.

Diseñado para ser consumido por una API central que gestione estado, claves y configuración.

## Estructura

```
wireguard-api/
├── api/
│   ├── main.py            # FastAPI app + auth por API Key
│   ├── config.py          # WG_API_KEY via env
│   ├── models/
│   │   ├── interfaces.py  # InterfaceResponse
│   │   └── peers.py       # PeerAdd, PeerResponse
│   ├── routers/
│   │   ├── interfaces.py  # up/down/save/show
│   │   └── peers.py       # add/remove/list/get
│   └── services/
│       └── wireguard.py   # Wrappers sobre wg/wg-quick
├── Dockerfile             # python:3.13-alpine + wireguard-tools
├── docker-compose.yml
├── entrypoint.sh          # IP forwarding + auto-up interfaces + API
└── requirements.txt
```

## Inicio rápido

```bash
cp .env.example .env
docker compose up -d --build
```

El fichero `.conf` de WireGuard debe existir previamente en el volumen `./config` (creado por la API central u otro mecanismo). El entrypoint levanta automáticamente todas las interfaces con `.conf` existente.

## API Endpoints

Todos bajo `/api/v1`. Si `WG_API_KEY` está configurada, incluye `X-API-Key` en los headers.

### Interfaces (CRUD + acciones)

| Método   | Ruta                             | Descripción                         |
|----------|----------------------------------|-------------------------------------|
| `GET`    | `/api/v1/interfaces`             | Listar interfaces activas           |
| `POST`   | `/api/v1/interfaces`             | Crear interfaz (escribe .conf + up) |
| `GET`    | `/api/v1/interfaces/{name}`      | Detalle de una interfaz             |
| `DELETE` | `/api/v1/interfaces/{name}`      | Eliminar interfaz (down + rm .conf) |
| `POST`   | `/api/v1/interfaces/{name}/up`   | `wg-quick up`                       |
| `POST`   | `/api/v1/interfaces/{name}/down` | `wg-quick down`                     |
| `POST`   | `/api/v1/interfaces/{name}/save` | `wg-quick save`                     |

### Peers (CRUD)

| Método   | Ruta                                             | Descripción       |
|----------|--------------------------------------------------|-------------------|
| `GET`    | `/api/v1/interfaces/{iface}/peers`               | Listar peers      |
| `POST`   | `/api/v1/interfaces/{iface}/peers`               | Crear peer        |
| `GET`    | `/api/v1/interfaces/{iface}/peers/{public_key}`  | Detalle de un peer|
| `PUT`    | `/api/v1/interfaces/{iface}/peers/{public_key}`  | Actualizar peer   |
| `DELETE` | `/api/v1/interfaces/{iface}/peers/{public_key}`  | Eliminar peer     |

### Otros

| Método | Ruta             | Descripción |
|--------|------------------|-------------|
| `GET`  | `/`              | Info API    |
| `GET`  | `/api/v1/health` | Health check|

### Ejemplos

```bash
# Crear interfaz
curl -X POST http://localhost:8000/api/v1/interfaces \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key" \
  -d '{"name": "wg0", "address": "10.0.0.1/24", "listen_port": 51820, "private_key": "..."}'

# Crear peer
curl -X POST http://localhost:8000/api/v1/interfaces/wg0/peers \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key" \
  -d '{"public_key": "abc123...", "allowed_ips": "10.0.0.2/32"}'

# Actualizar peer
curl -X PUT http://localhost:8000/api/v1/interfaces/wg0/peers/abc123... \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key" \
  -d '{"public_key": "abc123...", "allowed_ips": "10.0.0.2/32,10.0.1.0/24"}'

# Persistir cambios runtime a .conf
curl -X POST http://localhost:8000/api/v1/interfaces/wg0/save \
  -H "X-API-Key: your-secret-api-key"

# Eliminar peer
curl -X DELETE http://localhost:8000/api/v1/interfaces/wg0/peers/abc123... \
  -H "X-API-Key: your-secret-api-key"
```

## Configuración

| Variable     | Default | Descripción                  |
|--------------|---------|------------------------------|
| `WG_API_KEY` | (vacío) | API Key (si vacío, sin auth) |