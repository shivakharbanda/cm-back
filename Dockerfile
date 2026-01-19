# Build stage
FROM python:3.11-slim as builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml .
COPY .python-version .
COPY uv.lock* .

# Install dependencies
RUN uv sync --no-dev --no-install-project

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV SERVICE_TYPE=api

# Expose port
EXPOSE 8000

# Run migrations and start the application
CMD ["sh", "-c", "\
  if [ \"$SERVICE_TYPE\" = \"api\" ]; then \
    alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000; \
  elif [ \"$SERVICE_TYPE\" = \"worker\" ]; then \
    python -m app.worker; \
  else \
    echo \"Unknown SERVICE_TYPE: $SERVICE_TYPE\" && exit 1; \
  fi"]
