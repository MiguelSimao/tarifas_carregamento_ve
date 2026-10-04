import json
import os

import pytest
import yaml

from tariffs.compile import _cross_validate_tariff_doc
from tariffs.model import TariffDocument
from tariffs.supercharger import (
    UnknownSuperchargerStationError,
    compute_fingerprint,
    decode_days_bitmask,
    detect_missing_time_templates,
    extract_pricing_tier,
    extract_station_mapping,
    extract_supercharger_prices,
    format_time_template_name,
    inject_time_templates,
    minutes_to_hhmm,
    process_rates,
    update_tesla_yaml,
)


def test_minutes_to_hhmm():
    assert minutes_to_hhmm(0) == "00:00"
    assert minutes_to_hhmm(540) == "09:00"
    assert minutes_to_hhmm(1080) == "18:00"
    assert minutes_to_hhmm(1440, wrap_midnight=True) == "00:00"
    assert minutes_to_hhmm(1440, wrap_midnight=False) == "24:00"


def test_decode_days_bitmask():
    # 127 = 1111111b -> Mon..Sun (1..7)
    assert decode_days_bitmask(127) == [1, 2, 3, 4, 5, 6, 7]
    # 1 = Mon
    assert decode_days_bitmask(1) == [1]
    # 3 = Mon, Tue
    assert decode_days_bitmask(3) == [1, 2]


def test_extract_pricing_tier():
    raw_tier = {
        "pricingStatus": "available",
        "currency": "EUR",
        "pricingUnit": "kwh",
        "priceChangedAt": "2026-09-24T19:18:59.453Z",
        "prices": [
            {"days": 127, "start": 0, "end": 540, "price": 320000},
            {"days": 127, "start": 540, "end": 1440, "price": 410000},
        ],
        "minutePrices": [],
    }

    tier = extract_pricing_tier(raw_tier)
    assert tier is not None
    assert tier["status"] == "available"
    assert tier["currency"] == "EUR"
    assert tier["pricing_unit"] == "kwh"
    assert len(tier["rates"]) == 2

    rate1 = tier["rates"][0]
    assert rate1["start_time"] == "00:00"
    assert rate1["end_time"] == "09:00"
    assert rate1["price"] == 0.32
    assert rate1["price_micros"] == 320000

    rate2 = tier["rates"][1]
    assert rate2["start_time"] == "09:00"
    assert rate2["end_time"] == "00:00"
    assert rate2["end_time_raw"] == "24:00"
    assert rate2["price"] == 0.41


def test_extract_station_and_prices_filter():
    sample_data = {
        "schemaVersion": 2,
        "generatedAt": "2026-10-02T13:02:45.599Z",
        "exchangeRates": {"base": "EUR"},
        "stations": [
            {
                "id": "station_pt",
                "country": "PT",
                "name": "Station Portugal",
                "address": {
                    "city": "Lisbon",
                    "street": "Avenida",
                    "postalCode": "1000",
                },
                "lat": 38.7,
                "lon": -9.1,
                "stallCount": 8,
                "maxPowerKw": 250,
                "pricing": {
                    "tesla": {
                        "pricingStatus": "available",
                        "currency": "EUR",
                        "pricingUnit": "kwh",
                        "prices": [
                            {"days": 127, "start": 0, "end": 1440, "price": 280000}
                        ],
                    },
                    "nonTesla": None,
                },
            },
            {
                "id": "station_es",
                "country": "ES",
                "name": "Station Spain",
                "lat": 40.4,
                "lon": -3.7,
                "stallCount": 10,
                "maxPowerKw": 250,
                "pricing": {},
            },
        ],
    }

    # Filter PT
    pt_result = extract_supercharger_prices(sample_data, country="PT")
    assert "exchange_rates" not in pt_result
    assert "fingerprint" in pt_result["metadata"]
    assert "fingerprint" in pt_result["stations"][0]
    assert pt_result["metadata"]["total_extracted_stations"] == 1
    assert pt_result["metadata"]["total_source_stations"] == 2
    assert pt_result["stations"][0]["id"] == "station_pt"
    assert pt_result["stations"][0]["pricing"]["tesla"]["rates"][0]["price"] == 0.28
    assert pt_result["stations"][0]["pricing"]["non_tesla"] is None

    # No filter (all)
    all_result = extract_supercharger_prices(sample_data, country=None)
    assert all_result["metadata"]["total_extracted_stations"] == 2
    assert all_result["metadata"]["fingerprint"] != pt_result["metadata"]["fingerprint"]


def test_compute_fingerprint_detects_changes():
    data1 = [{"id": "st1", "price": 0.28}]
    data2 = [{"id": "st1", "price": 0.28}]
    data3 = [{"id": "st1", "price": 0.30}]

    fp1 = compute_fingerprint(data1)
    fp2 = compute_fingerprint(data2)
    fp3 = compute_fingerprint(data3)

    assert fp1 == fp2
    assert fp1 != fp3
    assert len(fp1) == 64  # SHA-256 hex string


def test_format_time_template_name():
    assert format_time_template_name("00:00", "04:00") == "time_00_04"
    assert format_time_template_name("22:00", "08:00") == "time_22_08"
    assert format_time_template_name("04:30", "10:15") == "time_0430_1015"
    assert format_time_template_name("00:00", "10:00") == "time_00_10"


def test_process_rates_all_day():
    rates = [{"start_minute": 0, "end_minute": 1440, "price": 0.51}]
    processed = process_rates(rates)
    assert len(processed) == 1
    assert processed[0]["price"] == 0.51
    assert processed[0]["time_template"] is None
    assert processed[0]["start_time"] is None


def test_process_rates_midnight_consolidation():
    rates = [
        {"start_minute": 0, "end_minute": 480, "start_time": "00:00", "end_time": "08:00", "price": 0.20},
        {"start_minute": 480, "end_minute": 1320, "start_time": "08:00", "end_time": "22:00", "price": 0.46},
        {"start_minute": 1320, "end_minute": 1440, "start_time": "22:00", "end_time": "00:00", "price": 0.20},
    ]
    processed = process_rates(rates)
    assert len(processed) == 2
    # Consolidated overnight interval is placed first
    assert processed[0]["price"] == 0.20
    assert processed[0]["time_template"] == "time_22_08"
    assert processed[0]["start_time"] == "22:00"
    assert processed[0]["end_time"] == "08:00"

    assert processed[1]["price"] == 0.46
    assert processed[1]["time_template"] == "time_08_22"


def test_process_rates_distinct_midnight_prices():
    rates = [
        {"start_minute": 0, "end_minute": 600, "start_time": "00:00", "end_time": "10:00", "price": 0.20},
        {"start_minute": 600, "end_minute": 1200, "start_time": "10:00", "end_time": "20:00", "price": 0.50},
        {"start_minute": 1200, "end_minute": 1440, "start_time": "20:00", "end_time": "00:00", "price": 0.45},
    ]
    processed = process_rates(rates)
    assert len(processed) == 3
    assert processed[0]["time_template"] == "time_00_10"
    assert processed[1]["time_template"] == "time_10_20"
    assert processed[2]["time_template"] == "time_20_00"


def test_extract_station_mapping():
    sample_yaml = """
_supercharger_mapping:
  "14182": tesla_matosinhos
  "vilarealsupercharger": tesla_ribeira_de_pena
"""
    mapping = extract_station_mapping(sample_yaml)
    assert mapping == {
        "14182": "tesla_matosinhos",
        "vilarealsupercharger": "tesla_ribeira_de_pena",
    }


def test_extract_station_mapping_missing_raises():
    sample_yaml = """
providers:
  - name: Tesla
"""
    with pytest.raises(ValueError, match="Could not find '_supercharger_mapping'"):
        extract_station_mapping(sample_yaml)


def test_detect_missing_time_templates():
    sample_yaml = """
_templates:
  time_00_04: &time_00_04
    time_restrictions:
    - start_time: "00:00"
      end_time: "04:00"
"""
    stations = [
        {
            "id": "14182",
            "pricing": {
                "tesla": {
                    "rates": [
                        {"start_minute": 0, "end_minute": 600, "start_time": "00:00", "end_time": "10:00", "price": 0.20},
                    ]
                }
            },
        }
    ]
    missing = detect_missing_time_templates(sample_yaml, stations)
    assert "time_00_10" in missing
    assert missing["time_00_10"] == ("00:00", "10:00")


def test_inject_time_templates():
    sample_yaml = """_templates:
  time_00_04: &time_00_04
    time_restrictions:
    - start_time: "00:00"
      end_time: "04:00"

providers:
- name: Tesla
"""
    missing = {"time_00_10": ("00:00", "10:00")}
    updated = inject_time_templates(sample_yaml, missing)
    assert "time_00_10: &time_00_10" in updated
    assert 'start_time: "00:00"' in updated
    assert 'end_time: "10:00"' in updated
    # providers: must still follow templates
    assert updated.index("time_00_10") < updated.index("providers:")


def test_unknown_station_throws_exception():
    sample_yaml = """_supercharger_mapping:
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
    networks: []
"""
    suc_data = {
        "stations": [
            {"id": "14182", "name": "Matosinhos"},
            {"id": "unmapped_station_999", "name": "Braga, Portugal"},
        ]
    }
    with pytest.raises(UnknownSuperchargerStationError) as exc_info:
        update_tesla_yaml(sample_yaml, suc_data)

    assert "unmapped_station_999" in str(exc_info.value)
    assert "Braga, Portugal" in str(exc_info.value)


def test_full_update_roundtrip_with_real_data():
    tesla_yaml_path = os.path.join("data", "pt", "tesla.yaml")
    suc_prices_path = os.path.join("data", "pt", "supercharger_prices.json")

    with open(tesla_yaml_path, "r", encoding="utf-8") as f:
        original_yaml = f.read()

    with open(suc_prices_path, "r", encoding="utf-8") as f:
        suc_data = json.load(f)

    updated_yaml = update_tesla_yaml(original_yaml, suc_data, target_path=tesla_yaml_path)

    # 1. Check time_00_10 is injected
    assert "time_00_10: &time_00_10" in updated_yaml

    # 2. Check MultiPass is preserved
    assert "- name: MultiPass" in updated_yaml
    assert "network_id: IONY" in updated_yaml

    # 3. Check Non-Member and Member have updated networks
    assert "MATOSINHOS NON_MEMBER" in updated_yaml
    assert "MATOSINHOS MEMBER" in updated_yaml

    # 4. Check Pydantic validation and cross-validation
    parsed = yaml.safe_load(updated_yaml)
    doc = TariffDocument.model_validate(parsed)
    _cross_validate_tariff_doc(doc, tesla_yaml_path)

    non_member = next(p for p in doc.providers[0].plans if p.name == "Non-Member")
    member = next(p for p in doc.providers[0].plans if p.name == "Member")
    multipass = next(p for p in doc.providers[0].plans if p.name == "MultiPass")

    assert len(non_member.networks) == 10
    assert len(member.networks) == 10
    assert len(multipass.networks) == 1
