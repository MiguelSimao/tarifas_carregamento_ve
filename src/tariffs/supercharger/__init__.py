"""Tesla Supercharger tariff extraction and updating module."""

from __future__ import annotations

from tariffs.supercharger.cli import main
from tariffs.supercharger.extract import (
    DEFAULT_OUTPUT_ALL,
    DEFAULT_OUTPUT_PT,
    DEFAULT_SOURCE_URL,
    compute_fingerprint,
    decode_days_bitmask,
    extract_pricing_tier,
    extract_station,
    extract_supercharger_prices,
    fetch_suc_data,
    minutes_to_hhmm,
    parse_minute_prices,
    parse_price_intervals,
)
from tariffs.supercharger.update import (
    DEFAULT_TARGET_PATH,
    UnknownSuperchargerStationError,
    detect_missing_time_templates,
    extract_station_mapping,
    format_time_template_name,
    generate_networks_block,
    get_template_comment,
    inject_time_templates,
    process_rates,
    update_tesla_yaml,
)

__all__ = [
    "DEFAULT_OUTPUT_ALL",
    "DEFAULT_OUTPUT_PT",
    "DEFAULT_SOURCE_URL",
    "DEFAULT_TARGET_PATH",
    "UnknownSuperchargerStationError",
    "compute_fingerprint",
    "decode_days_bitmask",
    "detect_missing_time_templates",
    "extract_pricing_tier",
    "extract_station",
    "extract_station_mapping",
    "extract_supercharger_prices",
    "fetch_suc_data",
    "format_time_template_name",
    "generate_networks_block",
    "get_template_comment",
    "inject_time_templates",
    "main",
    "minutes_to_hhmm",
    "parse_minute_prices",
    "parse_price_intervals",
    "process_rates",
    "update_tesla_yaml",
]
