# Aggregator Service Dockerfile
# Build from project root: docker build -f services/aggregator-service/Dockerfile -t aggregator-service .

FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy package metadata and source code (required together for pip install)
COPY pyproject.toml README.md /app/
COPY src/ /app/src/

# Install the layering_detection package (dependencies from pyproject.toml)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy service code and shared utilities
COPY services/aggregator-service/ /app/services/aggregator-service/
COPY services/shared/ /app/services/shared/

# Set working directory to service directory
WORKDIR /app/services/aggregator-service

# Install service dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create output and logs directories before switching to non-root user
# These directories will be mounted as volumes, but we ensure they exist with proper permissions
RUN mkdir -p /app/output /app/logs

# Create a non-root user with fixed UID/GID (1000:1000) for consistent permissions
# Fixed UID/GID ensures proper ownership when volumes are mounted from host
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g 1000 --create-home --shell /usr/sbin/nologin appuser && \
    chown -R appuser:appuser /app && \
    chmod 755 /app/output /app/logs

USER appuser

# Expose service port
EXPOSE 8003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8003/health', timeout=5).read()" || exit 1

# Run uvicorn server (via main.py to apply request size limits)
CMD ["python", "main.py"]

