"""
Helpers for loading traffic overlay data from public feeds.
Falls back to static sample segments when no provider key is configured.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Tuple
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings

LOGGER = logging.getLogger(__name__)

DHAKA_BBOX: Tuple[float, float, float, float] = (
    23.70,
    90.35,
    23.92,
    90.55,
)


def get_traffic_snapshot() -> Dict:
    """
    Return a feature collection describing current traffic incidents.
    """
    provider = settings.TRAFFIC_CONFIG.get("provider", "").lower()
    if provider == "tomtom":
        incidents = _tomtom_incidents()
    else:
        incidents = []

    if not incidents:
        incidents = _fallback_segments()
        source = "fallback-sample"
    else:
        source = provider

    return {
        "source": source,
        "features": incidents,
        "generated": datetime.now(timezone.utc).isoformat(),
    }


def _tomtom_incidents() -> List[Dict]:
    api_key = settings.TRAFFIC_CONFIG.get("tomtom_api_key")
    if not api_key:
        return []

    params = {
        "key": api_key,
        "bbox": ",".join(str(coord) for coord in DHAKA_BBOX),
        "fields": "incidents{type,geometry{type,coordinates},properties{iconCategory,events{description},startTime,endTime,severity}}",
        "language": "en-US",
        "timeValidityFilter": "ACTIVE",
    }

    url = f"https://api.tomtom.com/traffic/services/5/incidentDetails?{urlencode(params)}"
    try:
        with urlopen(url, timeout=settings.TRAFFIC_CONFIG.get("timeout_seconds", 4)) as response:
            payload = json.load(response)
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        LOGGER.warning("Traffic feed request failed: %s", error)
        return []

    incidents: List[Dict] = []
    for entry in payload.get("incidents", []):
        geometry = entry.get("geometry", {})
        coordinates = geometry.get("coordinates", [])
        if not coordinates:
            continue

        severity = entry.get("properties", {}).get("severity", "UNKNOWN")
        description = _assemble_description(entry)
        incidents.append(
            {
                "type": geometry.get("type", "LineString"),
                "coordinates": coordinates,
                "severity": severity,
                "description": description,
            }
        )
    return incidents


def _assemble_description(entry: Dict) -> str:
    props = entry.get("properties", {})
    events = props.get("events", [])
    parts = [event.get("description") for event in events if event.get("description")]
    return " | ".join(parts) or "Traffic incident"


def _fallback_segments() -> List[Dict]:
    """
    Lightweight mocked data that highlights a few busy Dhaka routes.
    """
    return [
        {
            "type": "LineString",
            "coordinates": [
                [90.398, 23.780],
                [90.404, 23.788],
                [90.412, 23.795],
                [90.419, 23.801],
            ],
            "severity": "MODERATE",
            "description": "Simulated congestion near Tejgaon Industrial Area.",
        },
        {
            "type": "LineString",
            "coordinates": [
                [90.365, 23.751],
                [90.376, 23.757],
                [90.388, 23.761],
                [90.397, 23.768],
            ],
            "severity": "HEAVY",
            "description": "Simulated gridlock on Mirpur Road toward Dhanmondi.",
        },
        {
            "type": "LineString",
            "coordinates": [
                [90.430, 23.824],
                [90.437, 23.803],
                [90.444, 23.785],
            ],
            "severity": "LIGHT",
            "description": "Smooth flow on Dhaka - Chittagong Highway segment.",
        },
    ]
