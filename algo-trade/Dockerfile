# ============================================================
# Multi-stage build: Python backend + Next.js frontend
# Railway exposes the Next.js frontend (PORT env var).
# Python backend runs internally on port 8181.
# Next.js rewrites /api/* → http://localhost:8181/*
# ============================================================

# Stage 1: Python dependencies
FROM python:3.11-slim AS py-builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Next.js standalone build
FROM node:20-slim AS fe-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
# Rewrites proxy /api/* → backend on localhost:8181 (baked in at build time)
ENV ALGO_API_URL=http://localhost:8181
ENV NEXT_PUBLIC_API_URL=http://localhost:8181
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Stage 3: Runtime — Python + Node.js in one container
FROM python:3.11-slim AS runtime

LABEL description="Algo-trade: Next.js dashboard + Python trading engine"

# Install Node.js 20
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash appuser
WORKDIR /app

# Python packages + source
COPY --from=py-builder /install /usr/local
COPY src/ ./src/
COPY sample_data/ ./sample_data/
COPY scripts/ ./scripts/
COPY config.yaml.template ./config.yaml.template
RUN cp config.yaml.template config.yaml

# Next.js standalone output (self-contained Node server)
COPY --from=fe-builder /app/.next/standalone ./frontend/
COPY --from=fe-builder /app/.next/static      ./frontend/.next/static

RUN mkdir -p data logs && chown -R appuser:appuser /app

COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

USER appuser

# Health check via Next.js → proxied to Python backend
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD node -e "require('http').get('http://localhost:' + (process.env.PORT||3000) + '/api/health', r => process.exit(r.statusCode < 500 ? 0 : 1)).on('error', () => process.exit(1))"

# Railway injects PORT for the public-facing Next.js server.
# Python backend runs internally on 8181 (not exposed).
EXPOSE 3000

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CONFIG_PATH=/app/config.yaml
ENV MODE=paper
ENV API_PORT=8181
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0

CMD ["./docker-entrypoint.sh"]
