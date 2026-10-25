#!/usr/bin/env python3
"""Publish manifold temperatures from TimescaleDB to Home Assistant over MQTT.

Reads the latest calibrated reading per sensor from `sensor_readings` and
publishes it with Home Assistant MQTT discovery, so HA creates one
temperature sensor per probe under a single "Heating Manifold" device.

temp-monitor is untouched: this service only reads the database.
"""
import json
import os
import signal
import sys
import time

import paho.mqtt.client as mqtt
import psycopg2

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://sensor_user:sensor_password@timescaledb:5432/sensor_data",
)
MQTT_HOST = os.getenv("MQTT_HOST", "")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER") or None
MQTT_PASS = os.getenv("MQTT_PASS") or None
DISCOVERY_PREFIX = os.getenv("HA_DISCOVERY_PREFIX", "homeassistant")
BASE_TOPIC = os.getenv("BASE_TOPIC", "heating/manifold")
PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", "30"))
# Readings older than this are treated as stale and not published.
MAX_AGE_SECONDS = int(os.getenv("MAX_AGE_SECONDS", "300"))

# sensor_id -> friendly name. Odd = flow, even = return.
# Override with SENSOR_NAMES='{"1": "Zone C flow", ...}' as a balena variable.
DEFAULT_NAMES = {
    1: "Zone C flow", 2: "Zone C return",
    3: "Zone B flow", 4: "Zone B return",
    5: "Zone A flow", 6: "Zone A return",
    7: "Zone D flow", 8: "Zone D return",
}

STATUS_TOPIC = f"{BASE_TOPIC}/status"
DEVICE = {
    "identifiers": ["heating_manifold"],
    "name": "Heating Manifold",
    "manufacturer": "DIY",
    "model": "8-channel Modbus temperature monitor",
}


def sensor_names():
    raw = os.getenv("SENSOR_NAMES", "").strip()
    if not raw:
        return DEFAULT_NAMES
    try:
        return {int(k): str(v) for k, v in json.loads(raw).items()}
    except (ValueError, AttributeError) as e:
        print(f"WARNING: bad SENSOR_NAMES ({e}); using defaults", flush=True)
        return DEFAULT_NAMES


def publish_discovery(client, names):
    for sid, name in names.items():
        uid = f"heating_manifold_sensor_{sid}"
        config = {
            "name": name,
            "unique_id": uid,
            "default_entity_id": f"sensor.{uid}",
            "state_topic": f"{BASE_TOPIC}/sensor/{sid}",
            "availability_topic": STATUS_TOPIC,
            "device_class": "temperature",
            "unit_of_measurement": "°C",
            "state_class": "measurement",
            "suggested_display_precision": 1,
            "expire_after": MAX_AGE_SECONDS,
            "device": DEVICE,
        }
        client.publish(
            f"{DISCOVERY_PREFIX}/sensor/{uid}/config", json.dumps(config), retain=True
        )
    print(f"Published discovery for {len(names)} sensors", flush=True)


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code != 0:
        print(f"MQTT connect failed: {reason_code}", flush=True)
        return
    print(f"Connected to MQTT {MQTT_HOST}:{MQTT_PORT}", flush=True)
    client.subscribe(f"{DISCOVERY_PREFIX}/status")
    publish_discovery(client, userdata["names"])
    client.publish(STATUS_TOPIC, "online", retain=True)


def on_message(client, userdata, msg):
    # HA republishes "online" on restart; resend discovery so entities come back.
    if msg.topic == f"{DISCOVERY_PREFIX}/status" and msg.payload == b"online":
        publish_discovery(client, userdata["names"])


LATEST_SQL = """
    SELECT DISTINCT ON (sensor_id) sensor_id, temperature_celsius
    FROM sensor_readings
    WHERE time > now() - make_interval(secs => %s)
    ORDER BY sensor_id, time DESC
"""


def main():
    if not MQTT_HOST:
        print("ERROR: MQTT_HOST is not set; set it as a balena service variable", flush=True)
        # Idle rather than crash-loop so the supervisor doesn't thrash.
        while True:
            time.sleep(3600)

    names = sensor_names()
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="heating-manifold-ha-mqtt",
        userdata={"names": names},
    )
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.will_set(STATUS_TOPIC, "offline", retain=True)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    def shutdown(*_):
        client.publish(STATUS_TOPIC, "offline", retain=True)
        client.loop_stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    conn = None
    while True:
        try:
            if conn is None or conn.closed:
                conn = psycopg2.connect(DATABASE_URL)
                conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(LATEST_SQL, (MAX_AGE_SECONDS,))
                rows = cur.fetchall()
            for sid, temp_c in rows:
                if sid in names:
                    client.publish(f"{BASE_TOPIC}/sensor/{sid}", f"{temp_c:.2f}")
            if os.getenv("HA_MQTT_DEBUG"):
                print(f"Published {len(rows)} readings", flush=True)
        except psycopg2.Error as e:
            print(f"DB error: {e}", flush=True)
            try:
                if conn:
                    conn.close()
            except Exception:
                pass
            conn = None
        time.sleep(PUBLISH_INTERVAL)


if __name__ == "__main__":
    main()
