FROM python:3.13-alpine

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN apk add --no-cache wireguard-tools iproute2

WORKDIR /app

COPY pyproject.toml .
COPY api/ api/
RUN pip install --no-cache-dir --no-compile .

EXPOSE 8000/tcp

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
