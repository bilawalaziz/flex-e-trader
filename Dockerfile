# ================== BUILDER STAGE ==================
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies needed to build Python packages (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and activate a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH=/app 

# Copy ONLY the requirements file first – this layer will be cached
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ================== RUNTIME STAGE ==================
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install only runtime libraries (libpq for psycopg2/asyncpg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Now copy the application code – this layer changes often
COPY ./app /app/app

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh


COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic

# start app
ENTRYPOINT ["/app/entrypoint.sh"]
