# file: Dockerfile
# ============================================================
# Multi-stage build for the algo-trade service.
# Stage 1: dependency installation
# Stage 2: minimal runtime image
# ============================================================

FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Runtime stage -----------------------------------------
FROM python:3.11-slim AS runtime

LABEL maintainer="algo-trade" \
      description="Algorithmic options trading system (paper-trade)" \
      version="0.1.0"

# Non-root user for security.
RUN useradd -m -s /bin/bash appuser

WORKDIR /app

# Copy installed packages from builder.
COPY --from=builder /install /usr/local

# Copy application source.
COPY src/ ./src/
COPY sample_data/ ./sample_data/
COPY scripts/ ./scripts/
COPY config.yaml.template ./config.yaml.template

# Default config (override by mounting config.yaml or setting env vars).
RUN cp config.yaml.template config.yaml

RUN chown -R appuser:appuser /app
USER appuser

# Health check via the API server.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" \
    || exit 1

EXPOSE 8080

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CONFIG_PATH=/app/config.yaml
ENV MODE=paper

ENTRYPOINT ["python", "-m", "src.cli.main"]
CMD ["--mode", "paper"]
