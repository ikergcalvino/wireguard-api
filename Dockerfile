FROM python:3.13-alpine

RUN apk add --no-cache \
    wireguard-tools \
    iptables \
    ip6tables

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ api/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 51820/udp
EXPOSE 8000/tcp

ENTRYPOINT ["./entrypoint.sh"]
