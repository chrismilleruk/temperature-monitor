import pytest
from hubitat_client import extract_trv_fields


@pytest.fixture
def sample_trv_device():
    """Sample TRV device from Hubitat Maker API."""
    return {
        "name": "Sonoff TRVZB",
        "label": "Good Room",
        "type": "Sonoff Zigbee TRV",
        "id": "45",
        "room": "Good room",
        "attributes": {
            "temperature": "17.6",
            "thermostatSetpoint": "19.0",
            "battery": "100",
            "healthStatus": "online",
            "thermostatOperatingState": "heating",
        },
    }


@pytest.fixture
def sample_device_missing_fields():
    """Sample device with missing optional fields."""
    return {
        "id": "50",
        "label": "Test Device",
        "attributes": {
            "temperature": "20.0",
        },
    }


@pytest.fixture
def sample_device_no_id():
    """Sample device without id (should be skipped)."""
    return {
        "label": "Bad Device",
        "attributes": {
            "temperature": "20.0",
        },
    }


def test_extract_trv_fields_happy_path(sample_trv_device):
    """Test extraction of all fields from a complete device."""
    result = extract_trv_fields(sample_trv_device)

    assert result["device_id"] == "45"
    assert result["label"] == "Good Room"
    assert result["room"] == "Good room"
    assert result["temperature"] == 17.6
    assert result["setpoint"] == 19.0
    assert result["battery"] == 100
    assert result["health_status"] == "online"
    assert result["operating_state"] == "heating"
    assert result["raw"] == sample_trv_device


def test_extract_trv_fields_missing_optional(sample_device_missing_fields):
    """Test extraction with missing optional fields."""
    result = extract_trv_fields(sample_device_missing_fields)

    assert result["device_id"] == "50"
    assert result["label"] == "Test Device"
    assert result["temperature"] == 20.0
    assert result["room"] is None
    assert result["battery"] is None
    assert result["health_status"] is None


def test_extract_trv_fields_no_device_id(sample_device_no_id):
    """Test extraction of device without id (should have None device_id)."""
    result = extract_trv_fields(sample_device_no_id)

    assert result["device_id"] is None
    assert result["label"] == "Bad Device"
    assert result["temperature"] == 20.0


def test_extract_trv_fields_invalid_temperature(sample_trv_device):
    """Test that invalid temperature values are converted to None."""
    sample_trv_device["attributes"]["temperature"] = "not-a-number"
    result = extract_trv_fields(sample_trv_device)

    assert result["temperature"] is None
    assert result["device_id"] == "45"  # other fields unaffected


def test_extract_trv_fields_invalid_battery(sample_trv_device):
    """Test that invalid battery values are converted to None."""
    sample_trv_device["attributes"]["battery"] = "unknown"
    result = extract_trv_fields(sample_trv_device)

    assert result["battery"] is None
    assert result["device_id"] == "45"  # other fields unaffected


def test_extract_trv_fields_empty_attributes(sample_trv_device):
    """Test extraction with empty attributes dict."""
    sample_trv_device["attributes"] = {}
    result = extract_trv_fields(sample_trv_device)

    assert result["device_id"] == "45"
    assert result["temperature"] is None
    assert result["setpoint"] is None
    assert result["battery"] is None


def test_extract_trv_fields_none_attributes(sample_trv_device):
    """Test extraction when attributes is None."""
    sample_trv_device["attributes"] = None
    result = extract_trv_fields(sample_trv_device)

    assert result["device_id"] == "45"
    assert result["temperature"] is None
    assert result["setpoint"] is None
    assert result["battery"] is None
