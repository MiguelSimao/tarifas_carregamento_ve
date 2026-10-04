"""Supercharger data extraction and parsing logic.

Fetches data from suc-tracker.eu (or a local file) and extracts structured
pricing data for both Tesla members/owners and non-members.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import urllib.request
from typing import Any

DEFAULT_SOURCE_URL = "https://suc-tracker.eu/data/europe.json"
DEFAULT_OUTPUT_ALL = os.path.join("data", "supercharger_prices.json")
DEFAULT_OUTPUT_PT = os.path.join("data", "pt", "supercharger_prices.json")


def minutes_to_hhmm(minutes: int, wrap_midnight: bool = True) -> str:
    """Convert minutes from midnight (0..1440) to HH:MM format.

    Args:
        minutes: Minute of the day (0 to 1440).
        wrap_midnight: If True, 1440 is represented as "00:00". If False, "24:00".
    """
    if minutes == 1440 and wrap_midnight:
        return "00:00"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def decode_days_bitmask(days_bitmask: int) -> list[int]:
    """Decode a 7-bit days bitmask to a list of weekday numbers (1=Monday .. 7=Sunday).

    127 (1111111b) represents all 7 days of the week [1, 2, 3, 4, 5, 6, 7].
    """
    days: list[int] = []
    for bit_index in range(7):
        if (days_bitmask >> bit_index) & 1:
            days.append(bit_index + 1)
    return days


def parse_price_intervals(raw_prices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse raw per-kWh price intervals into a clean structure."""
    intervals = []
    for item in raw_prices:
        start_min = item.get("start", 0)
        end_min = item.get("end", 1440)
        raw_price = item.get("price", 0)
        days = item.get("days", 127)

        intervals.append(
            {
                "start_minute": start_min,
                "end_minute": end_min,
                "start_time": minutes_to_hhmm(start_min, wrap_midnight=False),
                "end_time": minutes_to_hhmm(end_min, wrap_midnight=True),
                "end_time_raw": minutes_to_hhmm(end_min, wrap_midnight=False),
                "price": round(raw_price / 1_000_000, 4),
                "price_micros": raw_price,
                "days": days,
                "days_of_week": decode_days_bitmask(days),
            }
        )
    return intervals


def parse_minute_prices(raw_minute_prices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse raw per-minute price schedules and power tiers."""
    schedules = []
    for item in raw_minute_prices:
        start_min = item.get("start", 0)
        end_min = item.get("end", 1440)
        days = item.get("days", 127)
        tiers = []
        for tier in item.get("tiers", []):
            raw_price = tier.get("price", 0)
            tiers.append(
                {
                    "min_power_kw": tier.get("minPowerKw"),
                    "max_power_kw": tier.get("maxPowerKw"),
                    "price_per_minute": round(raw_price / 1_000_000, 4),
                    "price_micros": raw_price,
                }
            )

        schedules.append(
            {
                "start_minute": start_min,
                "end_minute": end_min,
                "start_time": minutes_to_hhmm(start_min, wrap_midnight=False),
                "end_time": minutes_to_hhmm(end_min, wrap_midnight=True),
                "days": days,
                "days_of_week": decode_days_bitmask(days),
                "tiers": tiers,
            }
        )
    return schedules


def extract_pricing_tier(tier_data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Extract pricing details for a single pricing tier (tesla or nonTesla)."""
    if not tier_data:
        return None

    status = tier_data.get("pricingStatus")
    currency = tier_data.get("currency")
    pricing_unit = tier_data.get("pricingUnit", "kwh")
    price_changed_at = tier_data.get("priceChangedAt")

    rates = parse_price_intervals(tier_data.get("prices", []))
    minute_rates = parse_minute_prices(tier_data.get("minutePrices", []))

    return {
        "status": status,
        "currency": currency,
        "pricing_unit": pricing_unit,
        "price_changed_at": price_changed_at,
        "rates": rates,
        "minute_rates": minute_rates,
    }


def compute_fingerprint(data: Any) -> str:
    """Compute a deterministic SHA-256 fingerprint hash for arbitrary data."""
    serialized = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def extract_station(station: dict[str, Any]) -> dict[str, Any]:
    """Extract station identity and pricing from raw station dictionary."""
    address_info = station.get("address") or {}
    pricing_info = station.get("pricing") or {}

    station_data = {
        "id": station.get("id"),
        "name": station.get("name"),
        "country": station.get("country"),
        "city": address_info.get("city"),
        "street": address_info.get("street"),
        "postal_code": address_info.get("postalCode"),
        "coordinates": {
            "lat": station.get("lat"),
            "lon": station.get("lon"),
        },
        "timezone": station.get("timezone"),
        "stall_count": station.get("stallCount"),
        "max_power_kw": station.get("maxPowerKw"),
        "lifecycle": station.get("lifecycle"),
        "pricing": {
            "tesla": extract_pricing_tier(pricing_info.get("tesla")),
            "non_tesla": extract_pricing_tier(pricing_info.get("nonTesla")),
        },
        "raw_pricing": pricing_info,
    }
    station_data["fingerprint"] = compute_fingerprint(station_data)
    return station_data


def fetch_suc_data(source: str) -> dict[str, Any]:
    """Load SUC tracker JSON data from URL or local file path."""
    if source.startswith(("http://", "https://")):
        req = urllib.request.Request(
            source,
            headers={
                "User-Agent": "tarifas-carregamento-ve/1.0 (https://github.com/MiguelSimao/tarifas_carregamento_ve)"
            },
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read().decode("utf-8")
        return json.loads(content)

    with open(source, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_supercharger_prices(
    raw_data: dict[str, Any],
    country: str | None = None,
    source_ref: str | None = None,
) -> dict[str, Any]:
    """Extract Supercharger prices from the parsed europe.json or pre-extracted data.

    Args:
        raw_data: Parsed dictionary from europe.json or already-extracted json.
        country: Optional 2-letter ISO country code filter (e.g. 'PT').
        source_ref: Optional string indicating the source URL or file.

    Returns:
        Structured dictionary containing extracted stations and metadata.
    """
    stations_raw = raw_data.get("stations", [])
    country_filter = country.strip().upper() if country else None

    # Handle already extracted structure if passed as input
    if stations_raw and "pricing" in stations_raw[0] and isinstance(stations_raw[0].get("pricing"), dict):
        first_pricing = stations_raw[0]["pricing"]
        if "tesla" in first_pricing and isinstance(first_pricing.get("tesla"), dict) and "rates" in (first_pricing.get("tesla") or {}):
            extracted_stations = []
            for s in stations_raw:
                st_country = (s.get("country") or "").upper()
                if country_filter and st_country != country_filter:
                    continue
                extracted_stations.append(s)

            stations_fingerprint = compute_fingerprint(extracted_stations)
            return {
                "metadata": {
                    **(raw_data.get("metadata") or {}),
                    "source": source_ref or (raw_data.get("metadata") or {}).get("source", DEFAULT_SOURCE_URL),
                    "extracted_at": datetime.datetime.now(datetime.UTC).isoformat(),
                    "country_filter": country_filter,
                    "total_extracted_stations": len(extracted_stations),
                    "total_source_stations": len(stations_raw),
                    "fingerprint": stations_fingerprint,
                },
                "stations": extracted_stations,
            }

    extracted_stations = []
    for s in stations_raw:
        st_country = (s.get("country") or "").upper()
        if country_filter and st_country != country_filter:
            continue
        extracted_stations.append(extract_station(s))

    stations_fingerprint = compute_fingerprint(extracted_stations)

    return {
        "metadata": {
            "source": source_ref or DEFAULT_SOURCE_URL,
            "generated_at": raw_data.get("generatedAt"),
            "extracted_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "schema_version": raw_data.get("schemaVersion"),
            "country_filter": country_filter,
            "total_extracted_stations": len(extracted_stations),
            "total_source_stations": len(stations_raw),
            "fingerprint": stations_fingerprint,
        },
        "stations": extracted_stations,
    }
