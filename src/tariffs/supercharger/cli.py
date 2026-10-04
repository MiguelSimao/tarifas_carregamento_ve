"""Command line interface for Supercharger data extraction and tariff updating."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys

from tariffs.supercharger.extract import (
    DEFAULT_OUTPUT_ALL,
    DEFAULT_OUTPUT_PT,
    DEFAULT_SOURCE_URL,
    extract_supercharger_prices,
    fetch_suc_data,
)
from tariffs.supercharger.update import (
    DEFAULT_TARGET_PATH,
    UnknownSuperchargerStationError,
    update_tesla_yaml,
)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint to extract Supercharger prices and optionally update tariffs."""
    parser = argparse.ArgumentParser(
        description="Extract Tesla Supercharger prices and optionally update tariffs."
    )
    parser.add_argument(
        "--source",
        "-s",
        default=DEFAULT_SOURCE_URL,
        help=f"URL or local path to europe.json or extracted JSON (default: {DEFAULT_SOURCE_URL})",
    )
    parser.add_argument(
        "--country",
        "-c",
        default=None,
        help="Optional ISO 2-letter country code filter (e.g. 'PT', 'ES').",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output path for extracted JSON (default depends on country filter).",
    )
    parser.add_argument(
        "--save-raw",
        metavar="PATH",
        default=None,
        help="Optional path to save the raw downloaded JSON payload.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation spaces (default: 2).",
    )
    parser.add_argument(
        "--update",
        "-u",
        action="store_true",
        default=False,
        help="Update the target tariffs YAML file (default: False).",
    )
    parser.add_argument(
        "--target",
        "-t",
        default=DEFAULT_TARGET_PATH,
        help=f"Path to target tariffs YAML file to update when --update is set (default: {DEFAULT_TARGET_PATH}).",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        default=False,
        help="Validate and print diff without writing changes to target file (enables --update in dry-run mode).",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress console progress output.",
    )

    args = parser.parse_args(argv)

    do_update = args.update or args.dry_run

    # If updating tariffs and no country filter specified with default PT target, default to PT
    country = args.country
    if do_update and not country and os.path.normpath(args.target) == os.path.normpath(DEFAULT_TARGET_PATH):
        country = "PT"

    # Determine default output file
    if args.output:
        output_path = args.output
    elif country and country.upper() == "PT":
        output_path = DEFAULT_OUTPUT_PT
    elif country:
        output_path = os.path.join("data", f"supercharger_prices_{country.lower()}.json")
    else:
        output_path = DEFAULT_OUTPUT_ALL

    if not args.quiet:
        print(f"Loading Supercharger data from: {args.source}")

    try:
        raw_data = fetch_suc_data(args.source)
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] Failed to load data from '{args.source}': {e}", file=sys.stderr)
        return 1

    if args.save_raw and not args.dry_run:
        raw_dir = os.path.dirname(args.save_raw)
        if raw_dir:
            os.makedirs(raw_dir, exist_ok=True)
        with open(args.save_raw, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=args.indent, ensure_ascii=False)
        if not args.quiet:
            print(f"Saved raw data to: {args.save_raw}")

    result = extract_supercharger_prices(
        raw_data=raw_data,
        country=country,
        source_ref=args.source,
    )

    if not args.dry_run:
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=args.indent, ensure_ascii=False)

    if not args.quiet:
        station_count = result["metadata"]["total_extracted_stations"]
        country_info = f" for country '{country.upper()}'" if country else ""
        fingerprint = result["metadata"]["fingerprint"]
        action_desc = "Simulated extraction of" if args.dry_run else "Successfully extracted"
        print(
            f"{action_desc} {station_count} Supercharger stations{country_info} into {output_path} (fingerprint: {fingerprint})"
        )

    # If --update or --dry-run is set, proceed to update the tariffs YAML file
    if do_update:
        if not os.path.exists(args.target):
            print(f"[ERROR] Target YAML file '{args.target}' not found.", file=sys.stderr)
            return 1

        with open(args.target, "r", encoding="utf-8") as f:
            original_yaml = f.read()

        try:
            updated_yaml = update_tesla_yaml(original_yaml, result, target_path=args.target)
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
            station_count = len(result.get("stations", []))
            print(
                f"Successfully updated Member and Non-Member plans in {args.target} for {station_count} stations."
            )

    return 0
