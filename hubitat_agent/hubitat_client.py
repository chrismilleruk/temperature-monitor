import os
import requests
from typing import List, Dict, Any


def build_api_url() -> str:
    api_url = os.getenv("HUBITAT_API_URL")
    if api_url:
        return api_url

    host = os.getenv("HUBITAT_HOST")
    token = os.getenv("HUBITAT_TOKEN")

    # Provide a safe, helpful error that indicates which variables are present
    # without printing any secret values (like tokens).
    host_set = bool(host)
    token_set = bool(token)
    if not (host_set and token_set):
        raise RuntimeError(
            "Hubitat configuration missing. Provide HUBITAT_API_URL or both HUBITAT_HOST and HUBITAT_TOKEN. "
            f"Env presence: HUBITAT_API_URL set: {bool(api_url)}, HUBITAT_HOST set: {host_set}, HUBITAT_TOKEN set: {token_set}"
        )

    # Example path used in the project: /apps/api/50/devices/all?access_token=...
    return f"http://{host}/apps/api/50/devices/all?access_token={token}"


def fetch_devices() -> List[Dict[str, Any]]:
    url = build_api_url()
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise RuntimeError("Unexpected Hubitat response: expected a list")
    return data


def extract_trv_fields(device: Dict[str, Any]) -> Dict[str, Any]:
    # Extract relevant fields; be tolerant of missing keys
    attributes = device.get("attributes", {}) or {}
    def as_float(v):
        try:
            return float(v) if v is not None else None
        except Exception:
            return None

    def as_int(v):
        try:
            return int(v) if v is not None else None
        except Exception:
            return None

    return {
        "device_id": str(device.get("id")) if device.get("id") is not None else None,
        "label": device.get("label"),
        "name": device.get("name"),
        "room": device.get("room"),
        "temperature": as_float(attributes.get("temperature")),
        "setpoint": as_float(attributes.get("thermostatSetpoint") or attributes.get("thermostatSetpoint")),
        "battery": as_int(attributes.get("battery")),
        "health_status": attributes.get("healthStatus"),
        "operating_state": attributes.get("thermostatOperatingState"),
        "raw": device,
    }
