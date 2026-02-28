# Dockerfile for Log Analyzer (Production)

# Stage 1: Build
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install dependencies to user directory
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN useradd -m -r appuser && \
    mkdir -p /app/logs && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Update PATH
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Copy application code
COPY . .
RUN chown -R appuser:appuser /app

USER appuser

# Expose API port
EXPOSE 5000

# Default command: Start API server with Gunicorn
# 4 workers, binding to 0.0.0.0:5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "api.server:create_app()"]
