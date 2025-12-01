FROM python:3.11-slim AS runtime

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install minimal build tools if needed (most deps are stdlib-only here)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy project files into the image
COPY . /app

# Install the package
RUN pip install --no-cache-dir .

# Create a non-root user and switch to it
RUN useradd --create-home appuser
USER appuser

# Default locations for input/output/logs inside the container
WORKDIR /app

# By default, expect:
# - input/transactions.csv mounted under /app/input
# - output/ and logs/ directories mounted under /app/output and /app/logs
CMD ["python", "-c", "from pathlib import Path; from layering_detection.runner import run_pipeline; run_pipeline(Path('input/transactions.csv'), Path('output'), Path('logs'))"]



