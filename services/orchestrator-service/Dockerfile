# Orchestrator Service Dockerfile
# Build from project root: docker build -f services/orchestrator-service/Dockerfile -t orchestrator-service .

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
COPY services/orchestrator-service/ /app/services/orchestrator-service/
COPY services/shared/ /app/services/shared/

# Set working directory to service directory
WORKDIR /app/services/orchestrator-service

# Install service dependencies (including httpx for HTTP client)
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user for security (no login shell)
RUN useradd --create-home --shell /usr/sbin/nologin appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose service port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5).read()" || exit 1

# Run uvicorn server (via main.py to apply request size limits)
CMD ["python", "main.py"]

