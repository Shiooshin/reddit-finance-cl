FROM python:3.12-slim

# System packages: awscli for S3 sync, curl/ca-certificates for network calls
RUN apt-get update && apt-get install -y --no-install-recommends \
        awscli \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Poetry — single source of truth for dependencies is pyproject.toml + poetry.lock
RUN pip install --no-cache-dir poetry==2.1.3

# Install Python dependencies (layer cached separately from source code).
# --without dev: skip pytest/mypy/ruff. --no-root: don't install the project itself
# (source is copied later; PYTHONPATH below makes it importable).
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false \
 && poetry install --without dev --no-root --no-interaction --no-ansi

# Install Playwright's pinned Chromium binary + all required system libraries
RUN playwright install chromium && playwright install-deps chromium

# Copy application source
COPY src/ src/
COPY run.py .

# Copy entrypoint script and application config
COPY entrypoint.sh .
COPY config.json .

RUN chmod +x entrypoint.sh

# Create data directory for DuckDB
RUN mkdir -p /app/data

ENV PYTHONPATH=/app/src

ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]
