#!/bin/sh
set -e

# Bring up any existing interfaces
for conf in /etc/wireguard/*.conf; do
    [ -f "${conf}" ] || continue
    iface=$(basename "${conf}" .conf)
    echo "Starting WireGuard interface ${iface}..."
    wg-quick up "${iface}" || echo "Warning: failed to start ${iface}"
done

echo "Starting API server..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
