import os
import time
import sys
import logging
from typing import List

from hubitat_client import fetch_devices, extract_trv_fields
from db import insert_trv_rows, init_database
from migrations import run_migrations

from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hubitat_agent")

# Debug toggle: set HUBITAT_DEBUG=1 or pass --debug to enable verbose/table output
DEBUG_ENV = os.getenv('HUBITAT_DEBUG', '')
DEBUG = (DEBUG_ENV.lower() in ('1', 'true', 'yes')) or ('--debug' in sys.argv)


def run_poll_once():
    try:
        devices = fetch_devices()
    except Exception as e:
        logger.exception("Failed to fetch devices: %s", e)
        return
    rows = []
    for d in devices:
        r = extract_trv_fields(d)
        if r.get("device_id") is None:
            continue
        rows.append(r)
    try:
        insert_trv_rows(rows)
        # If not in debug mode, print a compact single-line summary instead of extra logs
        if not DEBUG:
            ts = time.strftime('%Y-%m-%d %H:%M:%S')
            parts = []
            for r in rows:
                dev = r.get('device_id') or '(no-id)'
                temp = r.get('temperature')
                parts.append(f"{dev}:{temp}")
            logger.info("%s | %s", ts, ' '.join(parts))
        else:
            logger.info("Inserted %d device rows", len(rows))
    except Exception:
        logger.exception("Failed to write rows to DB")


def run_poll_loop(interval: int):
    logger.info("Starting poll loop (interval=%ds)", interval)
    while True:
        run_poll_once()
        time.sleep(interval)


def create_server_app():
    app = Flask(__name__)

    @app.route("/hubitat/events", methods=["POST"])
    def events():
        try:
            payload = request.get_json(force=True)
        except Exception:
            return "invalid json", 400
        # If payload is a list of devices, insert all; if single device, wrap
        devices = []
        if isinstance(payload, list):
            devices = payload
        elif isinstance(payload, dict):
            # Maker API event payloads vary; if 'device' key exists, use it
            if "device" in payload and isinstance(payload["device"], dict):
                devices = [payload["device"]]
            else:
                # try to treat as a device representation
                devices = [payload]
        else:
            return "unsupported payload", 400

        rows = []
        for d in devices:
            r = extract_trv_fields(d)
            if r.get("device_id") is None:
                continue
            rows.append(r)
        try:
            insert_trv_rows(rows)
        except Exception:
            logger.exception("Error inserting rows from webhook")
            return "db error", 500
        return jsonify({"inserted": len(rows)})

    return app


def main():
    # Ensure database schema is set up. Try migrations first; if they fail
    # fall back to a simple programmatic init to create the table.
    try:
        run_migrations()
    except Exception as e:
        logger.warning("run_migrations failed or skipped: %s", e)
        try:
            init_database()
            logger.info("Initialized database schema via init_database() fallback")
        except Exception as e2:
            logger.error("Failed to initialize database via fallback: %s", e2)
            raise

    mode = os.getenv("MODE", "poll")
    interval = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
    run_once = os.getenv("RUN_ONCE", "false").lower() in ("1", "true", "yes")

    logger.info("Debug mode: %s", DEBUG)

    if mode == "server":
        app = create_server_app()
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8080"))
        logger.info("Starting server mode on %s:%d", host, port)
        app.run(host=host, port=port)
        return

    # default: poll mode
    if run_once:
        run_poll_once()
    else:
        run_poll_loop(interval)


if __name__ == "__main__":
    main()
