from scripts.extract_supercharger_prices import (
    compute_fingerprint,
    decode_days_bitmask,
    extract_pricing_tier,
    extract_supercharger_prices,
    minutes_to_hhmm,
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
