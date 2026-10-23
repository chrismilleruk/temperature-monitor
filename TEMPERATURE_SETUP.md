# Temperature Monitoring Setup

This project monitors 8 DS18B20 temperature sensors connected via an R4DCB08 8-Bit RS485 Temperature Receiver using MODBUS RTU protocol.

## Hardware Requirements

### Components
1. **USB to RS485 Converter** - Waveshare USB TO RS485 (B) with CH343G chip
2. **Temperature Receiver** - DONGKER R4DCB08 8Bit RS485 Temperature Receiver (MODBUS)
3. **Temperature Sensors** - Up to 8 × DS18B20 waterproof temperature sensors (HALJIA or compatible)

### Wiring

#### USB to RS485 Adapter to R4DCB08
```
USB to RS485        R4DCB08
────────────        ───────
    A+      ────────  A
    B-      ────────  B
    GND     ────────  GND
```

#### Power for R4DCB08
- Connect **V+** to DC 6-24V (typically 12V or 24V)
- Connect **GND** to power supply ground

#### DS18B20 Sensors to R4DCB08
Each DS18B20 sensor connects to the numbered sensor ports on the R4DCB08:
- **Red wire (VCC)** → Sensor power terminal
- **Yellow wire (Data)** → Sensor data terminal  
- **Black wire (GND)** → Sensor ground terminal

The R4DCB08 supports up to 8 sensors. Each sensor is automatically assigned an address (1-8).

## Software Configuration

### Environment Variables

You can configure the temperature monitor using balena environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SERIAL_PORT` | `/dev/ttyUSB0` | Serial port for USB to RS485 adapter |
| `MODBUS_ADDRESS` | `1` | MODBUS device address of R4DCB08 |
| `BAUDRATE` | `9600` | Serial communication baudrate |
| `PARITY` | `N` | Parity bit (N=None, E=Even, O=Odd) |
| `STOPBITS` | `1` | Number of stop bits |
| `BYTESIZE` | `8` | Number of data bits |
| `TIMEOUT` | `3` | Communication timeout in seconds |
| `NUM_SENSORS` | `8` | Number of temperature sensors to read |
| `TEMP_START_REGISTER` | `0` | Starting MODBUS register for temperature data |
| `POLL_INTERVAL` | `5` | Seconds between temperature readings |

### Setting Variables in Balena Cloud

1. Navigate to your device or fleet in balena Cloud
2. Go to **Variables** section
3. Add variables with appropriate values
4. Changes take effect after the container restarts

### Local Development

For local testing, you can modify `config.env` or export environment variables before running.

## Deployment

### Production Deployment to Balena Device

```bash
# From the project directory
balena push <app-name>
```

### Local Development Mode

```bash
# Push to local device (uses dev stage with live reload)
balena push <device-ip>.local
```

### Building Specific Stages

```bash
# Build production stage
balena build --target prod -t temp-monitor:prod .

# Build dev stage
balena build --target dev -t temp-monitor:dev .
```

## Temperature Monitor Output

The application displays temperature readings every 5 seconds (configurable):

```
============================================================
DS18B20 Temperature Sensor Status
============================================================
Timestamp: 2025-11-11 22:30:15
------------------------------------------------------------
Sensor     Raw Value    °C           °F           Status
------------------------------------------------------------
Sensor 1   245          24.5°C       76.1°F       OK
Sensor 2   230          23.0°C       73.4°F       OK
Sensor 3   255          25.5°C       77.9°F       OK
Sensor 4   0            0.0°C        32.0°F       NOT CONNECTED
Sensor 5   220          22.0°C       71.6°F       OK
Sensor 6   N/A          N/A          N/A          NO DATA
Sensor 7   N/A          N/A          N/A          NO DATA
Sensor 8   N/A          N/A          N/A          NO DATA
============================================================
```

### Status Indicators

- **OK** - Sensor connected and reading within valid range (-55°C to 125°C)
- **NOT CONNECTED** - Sensor slot configured but no sensor detected (raw value = 0 or 0xFFFF)
- **OUT OF RANGE** - Temperature reading outside DS18B20 spec range
- **NO DATA** - MODBUS communication error or sensor not responding

## Troubleshooting

### No Connection to Serial Port

**Error:** `Failed to connect to /dev/ttyUSB0`

**Solutions:**
1. Verify USB to RS485 adapter is plugged in
2. Check device permissions: `ls -l /dev/ttyUSB*`
3. Try different serial port (may be `/dev/ttyUSB1`, `/dev/ttyACM0`, etc.)
4. Update `SERIAL_PORT` environment variable if needed
5. Ensure container has privileged access (already configured in docker-compose.yml)

### All Sensors Show "NOT CONNECTED"

**Causes:**
- DS18B20 sensors not connected to R4DCB08
- R4DCB08 not powered (needs 6-24V DC)
- Wrong MODBUS address

**Solutions:**
1. Check R4DCB08 power LED
2. Verify sensor wiring (Red=VCC, Yellow=Data, Black=GND)
3. Check MODBUS address - try updating `MODBUS_ADDRESS` environment variable
4. Test with a known working sensor first

### MODBUS Communication Errors

**Error:** `MODBUS read failed` or `MODBUS exception`

**Solutions:**
1. Verify RS485 wiring (A+ and B- not swapped)
2. Check baudrate matches R4DCB08 configuration (default 9600)
3. Ensure proper RS485 termination (120Ω resistor if needed for long cables)
4. Try lowering baudrate or increasing timeout

### Incorrect Temperature Readings

**Issue:** Temperature values seem wrong

**Solutions:**
1. R4DCB08 may use different encoding (0.1°C units vs direct celsius)
2. Check manufacturer documentation for register format
3. Modify conversion formula in `temp_monitor.py` if needed:
   ```python
   # Current: temp = raw_value / 10.0
   # Alternative: temp = raw_value  (for direct celsius)
   ```

## Testing Without Hardware

To test the application without actual hardware:

1. Use a USB-to-RS485 loopback adapter
2. Use MODBUS simulation software
3. Comment out the connection check in `temp_monitor.py` for dry-run testing

## DS18B20 Specifications

- **Temperature Range:** -55°C to +125°C
- **Accuracy:** ±0.5°C (-10°C to +85°C)
- **Resolution:** 9-12 bits (programmable)
- **Protocol:** 1-Wire digital interface
- **Power:** 3.0-5.5V DC

## R4DCB08 MODBUS Registers

The R4DCB08 typically uses MODBUS function 03 (Read Holding Registers):

- **Registers 0-7:** Temperature readings for sensors 1-8
- **Register format:** Signed 16-bit integer (typically 0.1°C units)

*Note: Exact register mapping may vary by firmware version. Consult manufacturer documentation or contact seller for AT/UART command reference.*

## Support & Resources

- [Waveshare USB TO RS485 (B) Wiki](https://www.waveshare.com/wiki/USB_TO_RS485_(B))
- See `DEVICES.md` for complete hardware specifications
- For R4DCB08 AT/UART commands, contact DONGKER seller post-purchase

---

# Home Assistant Integration

The `ha-mqtt` service reads the latest reading per sensor from TimescaleDB and
publishes it to Home Assistant over MQTT with discovery. HA creates a
"Heating Manifold" device with one temperature sensor per probe; no HA YAML is needed.

Set these as balena service variables on `ha-mqtt`:

| Variable | Example | Notes |
|---|---|---|
| `MQTT_HOST` | `192.168.x.x` | HA host if using the Mosquitto add-on |
| `MQTT_PORT` | `1883` | default 1883 |
| `MQTT_USER` / `MQTT_PASS` | | a dedicated HA user works with the Mosquitto add-on |
| `SENSOR_NAMES` | `{"1": "Zone C flow", ...}` | optional; defaults to zone A–D flow/return |
| `PUBLISH_INTERVAL` | `30` | seconds |
| `MAX_AGE_SECONDS` | `300` | readings older than this are not sent; HA marks sensors unavailable |

Topics: state on `heating/manifold/sensor/<id>`, availability on `heating/manifold/status`.
