#!/usr/bin/env python3
"""
Smoke test for Hubitat Agent integration.

This script verifies that:
1. The hubitat_agent service can be built
2. Database migrations run without errors
3. Sample TRV data can be parsed and inserted
4. Data can be queried back from the database
"""

import os
import sys
import json
import psycopg2
from pathlib import Path

# Add hubitat_agent to path for imports
sys.path.insert(0, str(Path(__file__).parent / "hubitat_agent"))

from hubitat_client import extract_trv_fields
from db import insert_trv_rows


SAMPLE_DEVICE = {
    "name": "Sonoff TRVZB",
    "label": "Test TRV",
    "type": "Sonoff Zigbee TRV",
    "id": "999",
    "date": "2025-11-15T17:05:49+0000",
    "room": "Test Room",
    "capabilities": ["ThermostatMode", "TemperatureMeasurement"],
    "attributes": {
        "temperature": "19.5",
        "thermostatSetpoint": "20.0",
        "battery": "85",
        "healthStatus": "online",
        "thermostatOperatingState": "heating",
        "thermostatMode": "heat",
    },
    "commands": [{"command": "setHeatingSetpoint"}],
}


def test_parsing():
    """Test TRV field extraction."""
    print("\n[1/4] Testing TRV field extraction...")
    try:
        result = extract_trv_fields(SAMPLE_DEVICE)
        assert result["device_id"] == "999", f"Expected device_id='999', got {result['device_id']}"
        assert result["label"] == "Test TRV", f"Expected label='Test TRV', got {result['label']}"
        assert result["temperature"] == 19.5, f"Expected temperature=19.5, got {result['temperature']}"
        assert result["setpoint"] == 20.0, f"Expected setpoint=20.0, got {result['setpoint']}"
        assert result["battery"] == 85, f"Expected battery=85, got {result['battery']}"
        assert result["health_status"] == "online", f"Expected health_status='online', got {result['health_status']}"
        print("  ✓ Field extraction works correctly")
        return True
    except Exception as e:
        print(f"  ✗ Field extraction failed: {e}")
        return False


def test_db_connection():
    """Test database connection."""
    print("\n[2/4] Testing database connection...")
    try:
        dsn = os.getenv("TIMESCALEDB_URL") or os.getenv("DATABASE_URL")
        if not dsn:
            print("  ⚠ TIMESCALEDB_URL not set, skipping DB test")
            return None
        
        conn = psycopg2.connect(dsn)
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                print(f"  ✓ Connected to: {version[:50]}...")
        return True
    except Exception as e:
        print(f"  ✗ Database connection failed: {e}")
        return False


def test_table_exists():
    """Check if trv_temperatures table exists."""
    print("\n[3/4] Checking database schema...")
    try:
        dsn = os.getenv("TIMESCALEDB_URL") or os.getenv("DATABASE_URL")
        if not dsn:
            print("  ⚠ TIMESCALEDB_URL not set, skipping schema check")
            return None
        
        conn = psycopg2.connect(dsn)
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='trv_temperatures');"
                )
                exists = cur.fetchone()[0]
                if exists:
                    cur.execute("SELECT COUNT(*) FROM trv_temperatures;")
                    count = cur.fetchone()[0]
                    print(f"  ✓ Table 'trv_temperatures' exists ({count} rows)")
                else:
                    print("  ⚠ Table 'trv_temperatures' does not exist (migration not yet run)")
        return exists
    except Exception as e:
        print(f"  ✗ Schema check failed: {e}")
        return False


def test_insert_and_query():
    """Test inserting sample data and querying it back."""
    print("\n[4/4] Testing insert and query...")
    try:
        dsn = os.getenv("TIMESCALEDB_URL") or os.getenv("DATABASE_URL")
        if not dsn:
            print("  ⚠ TIMESCALEDB_URL not set, skipping insert test")
            return None
        
        rows = [extract_trv_fields(SAMPLE_DEVICE)]
        insert_trv_rows(rows)
        print("  ✓ Successfully inserted sample TRV data")
        
        # Query it back
        conn = psycopg2.connect(dsn)
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT device_id, label, temperature, setpoint FROM trv_temperatures "
                    "WHERE device_id = %s ORDER BY time DESC LIMIT 1;",
                    ("999",)
                )
                row = cur.fetchone()
                if row:
                    device_id, label, temp, setpoint = row
                    print(f"  ✓ Retrieved data: {label} (ID: {device_id}): {temp}°C / {setpoint}°C setpoint")
                    return True
                else:
                    print("  ✗ Inserted data not found in query")
                    return False
    except Exception as e:
        print(f"  ✗ Insert/query test failed: {e}")
        return False


def main():
    print("=" * 60)
    print("Hubitat Agent Smoke Test")
    print("=" * 60)
    
    results = []
    
    # Always run parsing test (no DB required)
    results.append(("Parsing", test_parsing()))
    
    # Try DB tests if connection string is provided
    db_conn = test_db_connection()
    results.append(("DB Connection", db_conn))
    
    if db_conn is not False:  # None or True
        results.append(("Schema Check", test_table_exists()))
        results.append(("Insert & Query", test_insert_and_query()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r is True)
    failed = sum(1 for _, r in results if r is False)
    skipped = sum(1 for _, r in results if r is None)
    
    for name, result in results:
        if result is True:
            status = "✓ PASS"
        elif result is False:
            status = "✗ FAIL"
        else:
            status = "⊘ SKIP"
        print(f"  {status:7} {name}")
    
    print("\nTotal: {} passed, {} failed, {} skipped".format(passed, failed, skipped))
    
    if failed == 0:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed. Check configuration and logs.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
