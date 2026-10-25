FROM python:3.11-slim

WORKDIR /app

# Install runtime deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY hubitat_agent/requirements-hubitat.txt ./
RUN pip install --no-cache-dir -r requirements-hubitat.txt

# Copy agent code
COPY hubitat_agent/ /app/

# Copy migrations directory
COPY migrations/ /app/migrations/

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
