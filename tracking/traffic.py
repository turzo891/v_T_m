"""
Helpers for loading traffic overlay data from public feeds.
Falls back to static sample segments when no provider key is configured.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Tuple
import requests

from django.conf import settings

LOGGER = logging.getLogger(__name__)

DHAKA_BBOX: Tuple[float, float, float, float] = (   #for dhaka city bounding box
    90.30, # min long
    23.70, # min lat
    90.50, # max long
    23.90, # max lat
)


def get_traffic_snapshot() -> Dict:
    provider = settings.TRAFFIC_CONFIG.get("provider", "").lower()
    if provider == "tomtom":
        features = _tomtom_flow_segments()
    else:
        features = []

    if not features:
        features = _fallback_segments()
        source = "fallback-sample"
    else:
        source = provider

    return {
        "source": source,
        "features": features,
        "generated": datetime.now(timezone.utc).isoformat(),
    }


def _tomtom_flow_segments() -> List[Dict]:
    api_key = settings.TRAFFIC_CONFIG.get("tomtom_api_key")
    if not api_key:
        return []

    # Use the bounding box version of the flowSegmentData API
    # Note: The API expects lon,lat,lon,lat format
    bbox_str = f"{DHAKA_BBOX[0]},{DHAKA_BBOX[1]},{DHAKA_BBOX[2]},{DHAKA_BBOX[3]}"
    url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?key={api_key}&bbox={bbox_str}"

    LOGGER.info(f"Requesting TomTom traffic with URL: {url}")

    try:
        response = requests.get(url, timeout=settings.TRAFFIC_CONFIG.get("timeout_seconds", 5))
        response.raise_for_status()
        payload = response.json()
    except (requests.exceptions.RequestException, json.JSONDecodeError) as error:
        LOGGER.warning("TomTom traffic flow request failed: %s", error)
        return []

    features: List[Dict] = []
    if not payload or 'flowSegmentData' not in payload:
        return features

    for segment in payload['flowSegmentData']:
        coordinates = [[p['longitude'], p['latitude']] for p in segment.get('coordinates', {}).get('coordinate', [])]
        if not coordinates:
            continue

        free_flow_speed = segment.get('freeFlowSpeed', 100)
        current_speed = segment.get('currentSpeed', 100)

        if free_flow_speed > 0:
            ratio = current_speed / free_flow_speed
            if ratio < 0.4:
                severity = "HEAVY"
            elif ratio < 0.8:
                severity = "MODERATE"
            else:
                severity = "LIGHT"
        else:
            severity = "LIGHT"

        features.append(
            {
                "type": "LineString",
                "coordinates": coordinates,
                "severity": severity,
                "description": f"Current Speed: {current_speed} km/h",
            }
        )
    return features


def _fallback_segments() -> List[Dict]:
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
