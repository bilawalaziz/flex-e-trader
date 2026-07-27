#BUILDER Stage
FROM python:3.12-slim AS builder

WORKDIR /app

# install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH=/app 
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# RUNTIME Stage
FROM python:3.12-slim AS runtime

WORKDIR /app

# install only runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY ./app /app/app

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh


COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic

# start app
ENTRYPOINT ["/app/entrypoint.sh"]
