FROM python:3.15-alpine

# Runs as root on purpose: wg and wg-quick need root with CAP_NET_ADMIN, and
# /etc/wireguard is owned by root with 0600 config files.

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN apk add --no-cache wireguard-tools iproute2

WORKDIR /app

COPY pyproject.toml README.md ./
COPY api/ api/
RUN pip install --no-cache-dir --no-compile .

EXPOSE 8000/tcp

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:8000/health || exit 1

# uvicorn also reads UVICORN_ROOT_PATH from the environment (see the README).
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
