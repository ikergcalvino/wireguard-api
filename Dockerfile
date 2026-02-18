FROM python:3.13-alpine

RUN apk add --no-cache wireguard-tools iproute2

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ api/

EXPOSE 8000/tcp
