import json

from tariffs.supercharger import (
    DEFAULT_OUTPUT_ALL,
    DEFAULT_OUTPUT_PT,
    compute_fingerprint,
    decode_days_bitmask,
    extract_pricing_tier,
    extract_supercharger_prices,
    main,
    minutes_to_hhmm,
)


def test_supercharger_exports():
    # Ensure exported symbols are callable / present
    assert callable(minutes_to_hhmm)
    assert callable(decode_days_bitmask)
    assert callable(extract_pricing_tier)
    assert callable(compute_fingerprint)
    assert callable(extract_supercharger_prices)
    assert DEFAULT_OUTPUT_ALL.endswith("supercharger_prices.json")
    assert DEFAULT_OUTPUT_PT.endswith("supercharger_prices.json")


def test_main_cli_extract_only(tmp_path):
    source_file = tmp_path / "europe.json"
    source_data = {
        "schemaVersion": 2,
        "generatedAt": "2026-10-02T13:02:45.599Z",
        "stations": [
            {
                "id": "14182",
                "country": "PT",
                "name": "Matosinhos",
                "pricing": {
                    "tesla": {
                        "pricingStatus": "available",
                        "currency": "EUR",
                        "pricingUnit": "kwh",
                        "prices": [
                            {"days": 127, "start": 0, "end": 1440, "price": 280000}
                        ],
                    }
                },
            }
        ],
    }
    source_file.write_text(json.dumps(source_data), encoding="utf-8")

    out_file = tmp_path / "extracted.json"
    code = main([
        "--source", str(source_file),
        "--output", str(out_file),
        "--quiet",
    ])
    assert code == 0
    assert out_file.exists()

    with open(out_file, "r", encoding="utf-8") as f:
        extracted = json.load(f)
    assert len(extracted["stations"]) == 1
    assert extracted["stations"][0]["id"] == "14182"


def test_main_cli_with_update_and_dry_run(tmp_path):
    source_file = tmp_path / "europe.json"
    source_data = {
        "stations": [
            {
                "id": "14182",
                "country": "PT",
                "name": "Matosinhos",
                "pricing": {
                    "tesla": {
                        "prices": [
                            {"days": 127, "start": 0, "end": 1440, "price": 280000}
                        ],
                    },
                    "nonTesla": {
                        "prices": [
                            {"days": 127, "start": 0, "end": 1440, "price": 400000}
                        ],
                    },
                },
            }
        ],
    }
    source_file.write_text(json.dumps(source_data), encoding="utf-8")

    sample_target_yaml = """_supercharger_mapping:
  "14182": tesla_matosinhos

_templates:
  tesla_matosinhos: &tesla_matosinhos
    network_id: TSLA

providers:
- name: Tesla
  plans:
  - name: Non-Member
    networks:
    - <<: *tesla_matosinhos
  - name: Member
    networks:
    - <<: *tesla_matosinhos
  - name: MultiPass
    networks:
    - network_id: IONY
      tariffs:
      - type: DC
        price: 0.69
"""
    target_file = tmp_path / "tesla.yaml"
    target_file.write_text(sample_target_yaml, encoding="utf-8")
    out_file = tmp_path / "out.json"

    # Dry-run: should succeed and not modify target_file
    code = main([
        "--source", str(source_file),
        "--output", str(out_file),
        "--target", str(target_file),
        "--dry-run",
        "--quiet",
    ])
    assert code == 0
    assert target_file.read_text(encoding="utf-8") == sample_target_yaml

    # Update: should modify target_file
    code = main([
        "--source", str(source_file),
        "--output", str(out_file),
        "--target", str(target_file),
        "--update",
        "--quiet",
    ])
    assert code == 0
    updated_content = target_file.read_text(encoding="utf-8")
    assert "MATOSINHOS MEMBER" in updated_content
    assert "price: 0.28" in updated_content
    assert "MATOSINHOS NON_MEMBER" in updated_content
    assert "price: 0.40" in updated_content


def test_main_cli_unmapped_station_fails(tmp_path):
    source_file = tmp_path / "europe.json"
    source_data = {
        "stations": [
            {
                "id": "unknown_station_123",
                "country": "PT",
                "name": "Unknown Station",
                "pricing": {},
            }
        ],
    }
    source_file.write_text(json.dumps(source_data), encoding="utf-8")

    sample_target_yaml = """_supercharger_mapping:
  "14182": tesla_matosinhos

_templates:
  tesla_matosinhos: &tesla_matosinhos
    network_id: TSLA

providers:
- name: Tesla
  plans:
  - name: Non-Member
    networks: []
  - name: Member
    networks: []
  - name: MultiPass
    networks: []
"""
    target_file = tmp_path / "tesla.yaml"
    target_file.write_text(sample_target_yaml, encoding="utf-8")

    code = main([
        "--source", str(source_file),
        "--target", str(target_file),
        "--update",
        "--quiet",
    ])
    assert code == 2  # Returns 2 on UnknownSuperchargerStationError


def test_main_cli_module_execution():
    import subprocess
    import sys

    res = subprocess.run(
        [sys.executable, "-m", "tariffs.supercharger", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "Extract Tesla Supercharger prices" in res.stdout
