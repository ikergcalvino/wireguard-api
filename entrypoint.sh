#!/bin/sh
set -e

WG_INTERFACE="${WG_API_WG_INTERFACE:-wg0}"
WG_CONFIG_DIR="${WG_API_WG_CONFIG_DIR:-/etc/wireguard}"
WG_SERVER_IP="${WG_API_WG_SERVER_IP:-10.0.0.1}"
WG_SUBNET="${WG_API_WG_SUBNET:-10.0.0.0/24}"
WG_PORT="${WG_API_WG_PORT:-51820}"
CONF_FILE="${WG_CONFIG_DIR}/${WG_INTERFACE}.conf"

# Generate server keys if they don't exist
if [ ! -f "${WG_CONFIG_DIR}/server_private.key" ]; then
    echo "Generating server keys..."
    wg genkey | tee "${WG_CONFIG_DIR}/server_private.key" | wg pubkey > "${WG_CONFIG_DIR}/server_public.key"
    chmod 600 "${WG_CONFIG_DIR}/server_private.key"
fi

SERVER_PRIVKEY=$(cat "${WG_CONFIG_DIR}/server_private.key")

# Create WireGuard config if it doesn't exist
if [ ! -f "${CONF_FILE}" ]; then
    echo "Creating WireGuard config..."
    SUBNET_MASK=$(echo "${WG_SUBNET}" | cut -d'/' -f2)
    cat > "${CONF_FILE}" <<EOF
[Interface]
Address = ${WG_SERVER_IP}/${SUBNET_MASK}
ListenPort = ${WG_PORT}
PrivateKey = ${SERVER_PRIVKEY}
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
EOF
    chmod 600 "${CONF_FILE}"
fi

# Enable IP forwarding
echo 1 > /proc/sys/net/ipv4/ip_forward

# Start WireGuard
echo "Starting WireGuard interface ${WG_INTERFACE}..."
wg-quick up "${WG_INTERFACE}"

echo "Starting API server..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
