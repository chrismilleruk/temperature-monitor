import os
import psycopg2
from psycopg2.extras import Json
from typing import List, Dict, Any


def get_conn():
    dsn = os.getenv("TIMESCALEDB_URL") or os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("TIMESCALEDB_URL or DATABASE_URL must be set")
    return psycopg2.connect(dsn)


def init_database():
    """Create the `trv_temperatures` table if it doesn't exist.

    This is a small, idempotent fallback so the agent can run without
    running external migrations tooling. It will also try to convert the
    table into a TimescaleDB hypertable if the extension is available.
    """
    dsn = os.getenv("TIMESCALEDB_URL") or os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("TIMESCALEDB_URL or DATABASE_URL must be set to init database")

    conn = psycopg2.connect(dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS trv_temperatures (
                        time TIMESTAMPTZ NOT NULL,
                        device_id TEXT,
                        label TEXT,
                        room TEXT,
                        temperature DOUBLE PRECISION,
                        setpoint DOUBLE PRECISION,
                        battery INTEGER,
                        health_status TEXT,
                        operating_state TEXT,
                        raw JSONB
                    );
                    """
                )
                # Try to convert to hypertable (TimescaleDB) if available - ignore errors
                try:
                    cur.execute("SELECT create_hypertable('trv_temperatures', 'time', if_not_exists => TRUE);")
                except Exception:
                    pass
    finally:
        conn.close()
    return True


def insert_trv_rows(rows: List[Dict[str, Any]]):
    if not rows:
        return
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                sql = (
                    "INSERT INTO trv_temperatures"
                    " (time, device_id, label, room, temperature, setpoint, battery, health_status, operating_state, raw)"
                    " VALUES (now(), %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                )
                for r in rows:
                    cur.execute(
                        sql,
                        (
                            r.get("device_id"),
                            r.get("label"),
                            r.get("room"),
                            r.get("temperature"),
                            r.get("setpoint"),
                            r.get("battery"),
                            r.get("health_status"),
                            r.get("operating_state"),
                            Json(r.get("raw")),
                        ),
                    )
    finally:
        conn.close()
