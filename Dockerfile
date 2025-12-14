FROM python:3.11-slim AS runtime

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy package metadata and source code (required together for pip install)
# README.md is needed because pyproject.toml references it for package metadata
COPY pyproject.toml README.md /app/
COPY src/ /app/src/

# Install the package
RUN pip install --no-cache-dir .

# Create a non-root user and switch to it
RUN useradd --create-home appuser
USER appuser

# By default, expect:
# - input/transactions.csv mounted under /app/input
# - output/ and logs/ directories mounted under /app/output and /app/logs
CMD ["python", "-c", "from pathlib import Path; from layering_detection.orchestrator import run_pipeline; run_pipeline(Path('input/transactions.csv'), Path('output'), Path('logs'))"]



