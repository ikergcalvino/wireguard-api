FROM python:3.15-alpine

# Runs as root on purpose: wg and wg-quick need root with CAP_NET_ADMIN, and
# /etc/wireguard is owned by root with 0600 config files.

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    UVICORN_HOST=0.0.0.0 UVICORN_PORT=8000

RUN apk add --no-cache wireguard-tools iproute2

WORKDIR /app

COPY pyproject.toml README.md ./
COPY api/ api/
RUN pip install --no-cache-dir --no-compile .

EXPOSE 8000/tcp

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider "http://${UVICORN_HOST}:${UVICORN_PORT}/api/v1/health" || exit 1

# uvicorn reads UVICORN_HOST and UVICORN_PORT from the environment.
CMD ["uvicorn", "api.main:app"]
