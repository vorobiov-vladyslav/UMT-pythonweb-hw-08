FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install uv (single layer)
RUN pip install --no-cache-dir uv==0.11.7

# Cache deps in their own layer
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# App code
COPY main.py ./
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
