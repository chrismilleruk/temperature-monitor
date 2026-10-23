FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir psycopg2-binary==2.9.9 paho-mqtt==2.1.0

COPY ha_mqtt/main.py /app/main.py

ENV PYTHONUNBUFFERED=1
CMD ["python", "main.py"]
