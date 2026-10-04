"""Update Tesla Supercharger tariffs in data/pt/tesla.yaml from extracted pricing data.

Uses the output of scripts/extract_supercharger_prices.py (supercharger_prices.json)
and updates only the Non-Member and Member plans in data/pt/tesla.yaml, maintaining
_supercharger_mapping and dynamically adding time restriction templates.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from typing import Any

import yaml

from tariffs.compile import _cross_validate_tariff_doc
from tariffs.model import TariffDocument

DEFAULT_INPUT_PATH = os.path.join("data", "pt", "supercharger_prices.json")
DEFAULT_TARGET_PATH = os.path.join("data", "pt", "tesla.yaml")


class UnknownSuperchargerStationError(KeyError):
    """Raised when an unmapped Supercharger station ID is encountered in the source data."""


def format_time_template_name(start_time: str, end_time: str) -> str:
    """Format a template name for a given start and end time interval.

    Examples:
        "00:00", "04:00" -> "time_00_04"
        "22:00", "08:00" -> "time_22_08"
        "04:30", "10:00" -> "time_0430_1000"
    """
    sh, sm = start_time.split(":")
    eh, em = end_time.split(":")
    if sm == "00" and em == "00":
        return f"time_{sh}_{eh}"
    return f"time_{sh}{sm}_{eh}{em}"


def process_rates(rates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Process raw pricing interval rates into structured tariff definitions.

    Handles 24/7 all-day intervals and midnight wrap-around consolidation
    when the start-of-day and end-of-day rates have identical prices.
    """
    if not rates:
        return []

    # Single all-day rate (00:00 to 24:00 / 0 to 1440 min)
    if len(rates) == 1 and rates[0].get("start_minute") == 0 and rates[0].get("end_minute") == 1440:
        return [
            {
                "price": rates[0]["price"],
                "time_template": None,
                "start_time": None,
                "end_time": None,
            }
        ]

    first = rates[0]
    last = rates[-1]
    merged: list[dict[str, Any]] = []

    # Check if first (starts at 00:00) and last (ends at 24:00) have identical prices
    if (
        len(rates) > 1
        and first.get("start_minute") == 0
        and last.get("end_minute") == 1440
        and first.get("price") == last.get("price")
    ):
        start_time = last["start_time"]
        end_time = first["end_time"]
        merged.append(
            {
                "price": first["price"],
                "time_template": format_time_template_name(start_time, end_time),
                "start_time": start_time,
                "end_time": end_time,
            }
        )
        for r in rates[1:-1]:
            merged.append(
                {
                    "price": r["price"],
                    "time_template": format_time_template_name(r["start_time"], r["end_time"]),
                    "start_time": r["start_time"],
                    "end_time": r["end_time"],
                }
            )
    else:
        for r in rates:
            merged.append(
                {
                    "price": r["price"],
                    "time_template": format_time_template_name(r["start_time"], r["end_time"]),
                    "start_time": r["start_time"],
                    "end_time": r["end_time"],
                }
            )

    return merged


def extract_station_mapping(yaml_content: str) -> dict[str, str]:
    """Extract the _supercharger_mapping dictionary from tesla.yaml."""
    parsed = yaml.safe_load(yaml_content)
    if not isinstance(parsed, dict):
        raise TypeError("Target YAML content must be a dictionary.")

    raw_mapping = parsed.get("_supercharger_mapping")
    if not raw_mapping or not isinstance(raw_mapping, dict):
        raise ValueError("Could not find '_supercharger_mapping' block in target YAML file.")

    return {str(k): str(v) for k, v in raw_mapping.items()}


def detect_missing_time_templates(
    yaml_content: str, stations: list[dict[str, Any]]
) -> dict[str, tuple[str, str]]:
    """Identify any time restriction templates required by station rates that are not in _templates."""
    parsed = yaml.safe_load(yaml_content) or {}
    existing_templates = set((parsed.get("_templates") or {}).keys())

    missing: dict[str, tuple[str, str]] = {}
    for station in stations:
        pricing = station.get("pricing") or {}
        for plan_key in ("tesla", "non_tesla"):
            tier = pricing.get(plan_key)
            if not tier:
                continue
            rates = process_rates(tier.get("rates", []))
            for r in rates:
                template_name = r.get("time_template")
                if (
                    template_name
                    and template_name not in existing_templates
                    and template_name not in missing
                ):
                    missing[template_name] = (r["start_time"], r["end_time"])

    return missing


def inject_time_templates(
    yaml_content: str, missing_templates: dict[str, tuple[str, str]]
) -> str:
    """Inject newly required time restriction templates into the _templates block."""
    if not missing_templates:
        return yaml_content

    # Locate the start of the `providers:` section to insert before it
    providers_match = re.search(r"\nproviders:\s*\n", yaml_content)
    if not providers_match:
        raise ValueError("Could not find 'providers:' block in target YAML.")

    insert_pos = providers_match.start()
    template_entries: list[str] = []
    for template_name, (start_time, end_time) in sorted(missing_templates.items()):
        entry = (
            f"  {template_name}: &{template_name}\n"
            f"    time_restrictions:\n"
            f'    - start_time: "{start_time}"\n'
            f'      end_time: "{end_time}"\n'
        )
        template_entries.append(entry)

    insertion_text = "\n" + "\n".join(template_entries)
    return yaml_content[:insert_pos] + insertion_text + yaml_content[insert_pos:]


def get_template_comment(template_name: str) -> str:
    """Format a clean comment header for a location template."""
    name = template_name.removeprefix("tesla_")
    if name == "loule":
        return "LOULÉ"
    return name.upper()


def generate_networks_block(
    stations: list[dict[str, Any]],
    plan_key: str,
    mapping: dict[str, str],
    plan_label: str,
) -> str:
    """Generate the formatted YAML networks list for a plan (Non-Member or Member)."""
    # Order stations according to the order defined in _supercharger_mapping
    mapping_order = list(mapping.keys())
    sorted_stations = sorted(
        stations,
        key=lambda s: mapping_order.index(str(s["id"])) if str(s["id"]) in mapping_order else 999,
    )

    lines: list[str] = []
    for station in sorted_stations:
        st_id = str(station["id"])
        template_name = mapping[st_id]
        comment = get_template_comment(template_name)

        pricing = station.get("pricing") or {}
        tier = pricing.get(plan_key)
        if not tier or not tier.get("rates"):
            continue

        rates = process_rates(tier["rates"])
        lines.append(f"    # {comment} {plan_label}")
        lines.append(f"    - <<: *{template_name}")
        lines.append("      tariffs:")
        for r in rates:
            lines.append("      - type: DC")
            lines.append(f"        price: {r['price']:.2f}")
            if r.get("time_template"):
                lines.append(f"        <<: *{r['time_template']}")
        lines.append("")

    return "\n".join(lines).rstrip()


def update_tesla_yaml(yaml_content: str, suc_data: dict[str, Any]) -> str:
    """Update Non-Member and Member plans in tesla.yaml from extracted Supercharger data.

    Raises:
        UnknownSuperchargerStationError: If any station ID in the extracted data is unmapped.
    """
    stations = suc_data.get("stations", [])
    mapping = extract_station_mapping(yaml_content)

    # 1. Validate all station IDs; raise exception immediately if unknown
    for station in stations:
        st_id = str(station.get("id"))
        if st_id not in mapping:
            st_name = station.get("name", "Unknown Station")
            raise UnknownSuperchargerStationError(
                f"Unknown Supercharger station ID '{st_id}' ('{st_name}'). "
                f"New station detected! Please add a location template to _templates: "
                f"and register the mapping in _supercharger_mapping: inside data/pt/tesla.yaml."
            )

    # 2. Check and inject any missing time restriction templates
    missing_templates = detect_missing_time_templates(yaml_content, stations)
    updated_content = inject_time_templates(yaml_content, missing_templates)

    # 3. Generate updated networks blocks
    non_member_networks = generate_networks_block(stations, "non_tesla", mapping, "NON_MEMBER")
    member_networks = generate_networks_block(stations, "tesla", mapping, "MEMBER")

    # 4. Replace Non-Member networks block
    pattern_non_member = re.compile(
        r"(- name:\s*Non-Member.*?\n\s+networks:\s*\n)(.*?)(?=\n\s+- name:\s*Member)",
        re.DOTALL,
    )
    match_nm = pattern_non_member.search(updated_content)
    if not match_nm:
        raise ValueError("Could not locate Non-Member networks block in target YAML.")
    updated_content = (
        updated_content[: match_nm.start(2)]
        + non_member_networks
        + "\n"
        + updated_content[match_nm.end(2) :]
    )

    # 5. Replace Member networks block
    pattern_member = re.compile(
        r"(- name:\s*Member.*?\n\s+networks:\s*\n)(.*?)(?=\n\s+- name:\s*MultiPass)",
        re.DOTALL,
    )
    match_m = pattern_member.search(updated_content)
    if not match_m:
        raise ValueError("Could not locate Member networks block in target YAML.")
    updated_content = (
        updated_content[: match_m.start(2)]
        + member_networks
        + "\n"
        + updated_content[match_m.end(2) :]
    )

    # 6. Validate parsed document and cross-validate
    parsed_updated = yaml.safe_load(updated_content)
    doc = TariffDocument.model_validate(parsed_updated)
    _cross_validate_tariff_doc(doc, "data/pt/tesla.yaml")

    return updated_content


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Update Non-Member and Member plans in data/pt/tesla.yaml from supercharger_prices.json."
    )
    parser.add_argument(
        "--input",
        "-i",
        default=DEFAULT_INPUT_PATH,
        help=f"Path to extracted Supercharger JSON (default: {DEFAULT_INPUT_PATH})",
    )
    parser.add_argument(
        "--target",
        "-t",
        default=DEFAULT_TARGET_PATH,
        help=f"Path to tesla.yaml target file (default: {DEFAULT_TARGET_PATH})",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Validate and print diff without writing changes to target file.",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress console progress output.",
    )

    args = parser.parse_args(argv)

    if not os.path.exists(args.input):
        print(f"Error: Input JSON file '{args.input}' not found.", file=sys.stderr)
        return 1

    if not os.path.exists(args.target):
        print(f"Error: Target YAML file '{args.target}' not found.", file=sys.stderr)
        return 1

    with open(args.input, "r", encoding="utf-8") as f:
        suc_data = json.load(f)

    with open(args.target, "r", encoding="utf-8") as f:
        original_yaml = f.read()

    try:
        updated_yaml = update_tesla_yaml(original_yaml, suc_data)
    except UnknownSuperchargerStationError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] Failed to update {args.target}: {e}", file=sys.stderr)
        return 1

    if original_yaml == updated_yaml:
        if not args.quiet:
            print("No changes needed. Tariffs are already up-to-date.")
        return 0

    if args.dry_run:
        diff = difflib.unified_diff(
            original_yaml.splitlines(keepends=True),
            updated_yaml.splitlines(keepends=True),
            fromfile=f"a/{args.target}",
            tofile=f"b/{args.target}",
        )
        print("".join(diff))
        if not args.quiet:
            print("\nDry-run completed successfully. No files were written.")
        return 0

    with open(args.target, "w", encoding="utf-8") as f:
        f.write(updated_yaml)

    if not args.quiet:
        station_count = len(suc_data.get("stations", []))
        print(
            f"Successfully updated Member and Non-Member plans in {args.target} for {station_count} stations."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
