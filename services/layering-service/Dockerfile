# Layering Detection Service Dockerfile
# Build from project root: docker build -f services/layering-service/Dockerfile -t layering-service .

FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy package metadata and source code (required together for pip install)
COPY pyproject.toml README.md /app/
COPY src/ /app/src/

# Install the layering_detection package
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy service code and shared utilities
COPY services/layering-service/ /app/services/layering-service/
COPY services/shared/ /app/services/shared/

# Set working directory to service directory
WORKDIR /app/services/layering-service

# Install service dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose service port
EXPOSE 8001

# Health check (using curl which is available in slim images, or fallback to Python)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health', timeout=5).read()" || exit 1

# Run uvicorn server (via main.py to apply request size limits)
CMD ["python", "main.py"]

