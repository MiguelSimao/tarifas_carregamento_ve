import datetime

import pytest
import yaml

from tariffs.model import TariffDocument
from tariffs.validate import (
    _collect_tariff_warnings,
    _cross_validate_tariff_doc,
    _validate_file,
)


def _make_doc(
    *,
    provider_publish: bool = True,
    plan_publish: bool = True,
    source: dict | None = None,
    end_date: str | None = None,
) -> TariffDocument:
    provider: dict = {
        "name": "TestProvider",
        "publish": provider_publish,
        "plans": [
            {
                "name": "TestPlan",
                "publish": plan_publish,
                "end_date": end_date,
                "networks": [
                    {
                        "network_id": "NET1",
                        "tariffs": [{"type": "DC", "price": 0.50}],
                    }
                ],
            }
        ],
    }
    if source is not None:
        provider["source"] = source
    return TariffDocument.model_validate({"providers": [provider]})


def test_warnings_missing_source_and_last_checked():
    today = datetime.date(2026, 11, 27)

    doc_no_source = _make_doc(source=None)
    warnings = _collect_tariff_warnings(doc_no_source, "test.yaml", today=today)
    assert len(warnings) == 1
    assert "missing 'source.last_checked'" in warnings[0]

    # Even if last_updated is recent, missing last_checked should still warn
    doc_only_updated = _make_doc(source={"last_updated": "2026-11-26"})
    warnings = _collect_tariff_warnings(doc_only_updated, "test.yaml", today=today)
    assert len(warnings) == 1
    assert "missing 'source.last_checked'" in warnings[0]


def test_warnings_last_checked_freshness():
    today = datetime.date(2026, 11, 27)

    # Exactly 30 days ago: should not warn
    doc_30_days = _make_doc(source={"last_checked": "2026-10-28"})
    assert _collect_tariff_warnings(doc_30_days, "test.yaml", today=today) == []

    # 31 days ago: should warn
    doc_31_days = _make_doc(source={"last_checked": "2026-10-27"})
    warnings = _collect_tariff_warnings(doc_31_days, "test.yaml", today=today)
    assert len(warnings) == 1
    assert "over a month" in warnings[0]
    assert "31 days ago" in warnings[0]


def test_warnings_invalid_last_checked_and_unpublished_provider():
    today = datetime.date(2026, 11, 27)

    doc_invalid = _make_doc(source={"last_checked": "not-a-date"})
    warnings = _collect_tariff_warnings(doc_invalid, "test.yaml", today=today)
    assert len(warnings) == 1
    assert "invalid 'source.last_checked'" in warnings[0]

    doc_unpub = _make_doc(provider_publish=False, source=None)
    assert _collect_tariff_warnings(doc_unpub, "test.yaml", today=today) == []


def test_cross_validate_lapsed_end_date():
    today = datetime.date(2026, 11, 27)

    # Yesterday -> fails
    doc_lapsed = _make_doc(end_date="2026-11-26")
    with pytest.raises(ValueError, match="has lapsed"):
        _cross_validate_tariff_doc(doc_lapsed, "test.yaml", today=today)

    # Today -> still valid
    doc_today = _make_doc(end_date="2026-11-27")
    _cross_validate_tariff_doc(doc_today, "test.yaml", today=today)

    # Future -> valid
    doc_future = _make_doc(end_date="2026-12-31")
    _cross_validate_tariff_doc(doc_future, "test.yaml", today=today)

    # Invalid format -> fails
    doc_bad_date = _make_doc(end_date="2026/11/26")
    with pytest.raises(ValueError, match="invalid end_date"):
        _cross_validate_tariff_doc(doc_bad_date, "test.yaml", today=today)

    # Unpublished plan or provider -> skipped
    _cross_validate_tariff_doc(
        _make_doc(plan_publish=False, end_date="2020-01-01"),
        "test.yaml",
        today=today,
    )
    _cross_validate_tariff_doc(
        _make_doc(provider_publish=False, end_date="2020-01-01"),
        "test.yaml",
        today=today,
    )


def test_validate_file_warns_without_failing_and_fails_on_lapsed(tmp_path, capsys):
    stale_file = tmp_path / "stale.yaml"
    stale_file.write_text(
        yaml.dump(
            {
                "providers": [
                    {
                        "name": "StaleProvider",
                        "source": {"last_checked": "2020-01-01"},
                        "plans": [
                            {
                                "name": "Base",
                                "networks": [
                                    {
                                        "network_id": "NET1",
                                        "tariffs": [{"type": "DC", "price": 0.5}],
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert _validate_file(str(stale_file)) is True
    captured = capsys.readouterr()
    assert "[WARN]" in captured.out
    assert "[OK]" in captured.out

    lapsed_file = tmp_path / "lapsed.yaml"
    lapsed_file.write_text(
        yaml.dump(
            {
                "providers": [
                    {
                        "name": "LapsedProvider",
                        "source": {"last_checked": "2026-11-26"},
                        "plans": [
                            {
                                "name": "Promo",
                                "end_date": "2020-01-01",
                                "networks": [
                                    {
                                        "network_id": "NET1",
                                        "tariffs": [{"type": "DC", "price": 0.5}],
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert _validate_file(str(lapsed_file)) is False
    captured = capsys.readouterr()
    assert "[ERROR]" in captured.out
    assert "has lapsed" in captured.out
