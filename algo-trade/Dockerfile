# ============================================================
# Single-stage Python build.
# Railway exposes the Python aiohttp server directly (PORT env var).
# Dashboard served at / — no Node.js required.
# ============================================================

# Stage 1: Python dependencies
FROM python:3.11-slim AS py-builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim AS runtime

LABEL description="Algo-trade: Python trading engine with built-in dashboard"

RUN useradd -m -s /bin/bash appuser
WORKDIR /app

COPY --from=py-builder /install /usr/local
COPY src/ ./src/
COPY sample_data/ ./sample_data/
COPY scripts/ ./scripts/
COPY config.yaml.template ./config.yaml.template
RUN cp config.yaml.template config.yaml

RUN mkdir -p data logs && chown -R appuser:appuser /app

COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

USER appuser

# Health check hits the Python aiohttp server directly.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,os; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT','8181') + '/health')"

EXPOSE 8181

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CONFIG_PATH=/app/config.yaml
ENV MODE=paper
ENV API_PORT=8181

CMD ["./docker-entrypoint.sh"]
