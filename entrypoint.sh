#!/bin/sh
set -e

WG_CONFIG_DIR="${WG_API_WG_CONFIG_DIR:-/etc/wireguard}"

# Enable IP forwarding
echo 1 > /proc/sys/net/ipv4/ip_forward

# Bring up any existing interfaces
for conf in "${WG_CONFIG_DIR}"/*.conf; do
    [ -f "${conf}" ] || continue
    iface=$(basename "${conf}" .conf)
    echo "Starting WireGuard interface ${iface}..."
    wg-quick up "${iface}" || echo "Warning: failed to start ${iface}"
done

echo "Starting API server..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
