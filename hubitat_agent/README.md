# Hubitat Agent

A lightweight Python service that integrates with Hubitat Elevation's Maker API to fetch TRV (Thermostat) data and store it in TimescaleDB for historical analysis and visualization.

## Features

- **Dual Mode**: Continuous polling or webhook listener (POST events)
- **TRV Data Collection**: Extracts temperature, setpoint, battery, health status, and operating state from Sonoff TRV and other thermostat devices
- **Time-Series Storage**: Inserts data into TimescaleDB for efficient querying and aggregation
- **Robust Error Handling**: Graceful handling of network and parsing errors with retry logic
- **Automatic Migrations**: Runs database schema on startup
- **Flexible Configuration**: Environment-based configuration for Hubitat API and database connection

## Configuration

Set the following environment variables:

### Hubitat API Connection (choose one method)

**Method 1: Full API URL** (recommended if you have the complete URL)
```bash
HUBITAT_API_URL=http://192.168.10.109/apps/api/50/devices/all?access_token=<token>
```

**Method 2: Host + Token** (build URL automatically)
```bash
HUBITAT_HOST=192.168.10.109
HUBITAT_TOKEN=cab9d803-e74b-443d-a81c-bba57d8b274b
```

### Database Connection
```bash
TIMESCALEDB_URL=postgresql://sensor_user:sensor_password@timescaledb:5432/sensor_data
# OR use DATABASE_URL (fallback)
DATABASE_URL=postgresql://sensor_user:sensor_password@timescaledb:5432/sensor_data
```

### Agent Mode
```bash
MODE=poll              # 'poll' for continuous polling (default), 'server' for webhook
POLL_INTERVAL_SECONDS=60  # How often to poll (default: 60)
RUN_ONCE=false         # Set to 'true' to fetch once and exit
```

### Server Mode (if MODE=server)
```bash
HOST=0.0.0.0
PORT=8080
```

## Running

### Docker Compose (Recommended)

The service is defined in `docker-compose.yml`:

```bash
docker-compose up -d hubitat-agent
```

The service will automatically:
1. Run database migrations on startup
2. Start polling or listening for webhooks based on `MODE`

### Direct Python (Development)

```bash
pip install -r requirements-hubitat.txt
export HUBITAT_API_URL="http://192.168.10.109/apps/api/50/devices/all?access_token=..."
export TIMESCALEDB_URL="postgresql://sensor_user:sensor_password@localhost:5432/sensor_data"
python main.py
```

**One-time run:**
```bash
RUN_ONCE=true python main.py
```

## Modes

### Poll Mode (default)
Continuously fetches all devices from the Hubitat API at regular intervals.

```bash
MODE=poll POLL_INTERVAL_SECONDS=60 python main.py
```

### Server Mode
Starts a Flask HTTP server that listens for Hubitat Maker API event webhooks.

To use this, configure the Hubitat Maker API to POST device events to:
```
http://<agent-host>:8080/hubitat/events
```

The agent will accept both:
- Single device events: `{"id": "45", "label": "Room", ...}`
- Device arrays: `[{...}, {...}]`
- Wrapped events: `{"device": {...}}`

## Database Schema

The agent uses a single table: `trv_temperatures`

| Column | Type | Description |
|--------|------|-------------|
| time | timestamptz | Timestamp of the reading |
| device_id | text | Unique device identifier |
| label | text | Device label/name |
| room | text | Room assignment |
| temperature | float | Current temperature (°C) |
| setpoint | float | Target temperature setpoint (°C) |
| battery | int | Battery percentage (0-100) |
| health_status | text | Device health status ('online', 'offline', etc.) |
| operating_state | text | Current operating state ('heating', 'idle', 'cooling') |
| raw | jsonb | Full device object (for debugging) |

The table is a TimescaleDB hypertable partitioned by time.

## Testing

Run unit tests:

```bash
pip install pytest
pytest test_hubitat_client.py -v
```

Tests cover:
- Extraction of TRV fields from sample device JSON
- Handling of missing optional fields
- Type conversion (temperature, battery, etc.)
- Invalid data handling

## Querying Data

Connect to TimescaleDB and query recent readings:

```bash
docker-compose exec timescaledb psql -U sensor_user -d sensor_data

SELECT * FROM trv_temperatures 
ORDER BY time DESC LIMIT 20;

SELECT device_id, label, room, AVG(temperature) as avg_temp, MAX(battery) as battery
FROM trv_temperatures
WHERE time > now() - interval '1 day'
GROUP BY device_id, label, room;
```

## Troubleshooting

### Service won't start: "HUBITAT_API_URL or HUBITAT_HOST+HUBITAT_TOKEN must be provided"
Ensure you set either `HUBITAT_API_URL` or both `HUBITAT_HOST` and `HUBITAT_TOKEN`.

### "TIMESCALEDB_URL or DATABASE_URL must be set"
Set the database connection string in environment.

### "Failed to fetch devices"
Check that the Hubitat API URL is correct and reachable. Verify the access token is valid.

### No data appearing in database
1. Check service logs: `docker-compose logs hubitat-agent`
2. Verify database connectivity: `docker-compose exec hubitat-agent bash`
3. Test the API endpoint manually:
   ```bash
   curl "http://192.168.10.109/apps/api/50/devices/all?access_token=..."
   ```

## Architecture

```
┌─────────────────────────────────────────┐
│       Hubitat Elevation Hub             │
│   (Maker API / Zigbee Devices)          │
└────────────┬────────────────────────────┘
             │
             │ HTTP GET (poll mode)
             │ or POST webhooks (server mode)
             │
             ▼
┌─────────────────────────────────────────┐
│      hubitat-agent (Python)             │
│                                         │
│  main.py (poll/server orchestration)    │
│  hubitat_client.py (API fetch+parse)    │
│  db.py (TimescaleDB writes)             │
│  migrations.py (schema setup)           │
└────────────┬────────────────────────────┘
             │
             │ INSERT (time-series data)
             │
             ▼
┌─────────────────────────────────────────┐
│         TimescaleDB (PostgreSQL)        │
│                                         │
│    trv_temperatures (hypertable)        │
└─────────────────────────────────────────┘
             │
             │ Query
             │
             ▼
┌─────────────────────────────────────────┐
│   Grafana / Applications (Dashboard)    │
└─────────────────────────────────────────┘
```

## Development

### Adding new device attributes

Edit `hubitat_client.extract_trv_fields()` to extract additional fields:

```python
def extract_trv_fields(device: Dict[str, Any]) -> Dict[str, Any]:
    attributes = device.get("attributes", {}) or {}
    return {
        # ... existing fields ...
        "my_new_field": attributes.get("myNewAttribute"),
    }
```

Then update the database schema in `migrations/001_create_trv_temperatures.sql`.

### Updating polling interval

Set `POLL_INTERVAL_SECONDS` to any value (in seconds). Common values:
- `30` - every 30 seconds (frequent updates)
- `60` - every minute (balanced, default)
- `300` - every 5 minutes (low bandwidth)

### Future enhancements

- [ ] Rate-limit handling from Hubitat API
- [ ] Change detection (only insert on value change)
- [ ] Webhook signature verification
- [ ] Exponential backoff for transient errors
- [ ] Metrics/observability (Prometheus endpoint)
- [ ] Support for other device types (not just TRVs)

## License

Same as parent project.
