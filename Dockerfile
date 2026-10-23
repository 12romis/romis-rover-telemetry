FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
RUN pip install .

# Команду задає сервіс у docker-compose.yml: ingest або web.
CMD ["python", "-m", "rover_telemetry.web"]
