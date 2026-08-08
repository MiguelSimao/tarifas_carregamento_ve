import os

import pytest
import yaml
from pydantic import ValidationError

from tarifas.model import (
    Network,
    Plan,
    Provider,
    Tariff,
    TariffDocument,
    TariffTier,
    TimeRestriction,
)


def test_template_yaml_validates():
    """Ensure that the template.yaml file perfectly matches the model schema."""
    template_path = os.path.join(
        os.path.dirname(__file__), "..", "src", "tarifas", "template.yaml"
    )
    assert os.path.exists(template_path), "Template file missing"

    with open(template_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Should not raise validation error
    doc = TariffDocument.model_validate(data)

    # Basic structural assertions
    assert len(doc.providers) > 0

    # Locate a specific plan and verify newly added fields like cashback
    plan_base = next(p for p in doc.providers[0].plans if p.name == "PlanName")
    assert plan_base.cashback == 0.0

    # Locate a network to verify locations and time restrictions
    mobie_network = next(n for n in plan_base.networks if n.network_id == "NetworkName")
    assert "LOC-00001" in mobie_network.included_locations
    assert "LOC-00002" in mobie_network.excluded_locations

    ac_tariff = next(t for t in mobie_network.tariffs if t.type == "AC")
    assert ac_tariff.time_restrictions is not None
    assert len(ac_tariff.time_restrictions) == 1
    assert ac_tariff.time_restrictions[0].start_time == "08:00"
    assert ac_tariff.time_restrictions[0].end_time == "20:00"
    assert ac_tariff.time_restrictions[0].days_of_week == [6, 7]


def test_tariff_requires_price_or_tiers():
    """Ensure a Tariff has either price or tiers."""
    with pytest.raises(
        ValidationError, match='Either "price" or "tiers" must be provided in a tariff'
    ):
        Tariff(type="AC", unit="energy")


def test_tariff_with_price():
    """Tariff with price is valid."""
    t = Tariff(type="AC", price=0.40, unit="energy")
    assert t.price == 0.40
    assert t.tiers is None


def test_tariff_with_tiers():
    """Tariff with tiers is valid."""
    t = Tariff(
        type="DC",
        tiers=[
            TariffTier(max=50.0, price=0.58),
            TariffTier(min=50.0, max=150.0, price=0.68),
        ],
    )
    assert t.price is None
    assert len(t.tiers) == 2


def test_time_restrictions_model():
    """Test the TimeRestriction model instantiation."""
    tr = TimeRestriction(start_time="08:00", end_time="20:00", days_of_week=[6, 7])
    assert tr.start_time == "08:00"
    assert tr.end_time == "20:00"
    assert tr.days_of_week == [6, 7]


def test_network_locations():
    """Test included/excluded locations on a Network."""
    n = Network(
        network_id="Test",
        included_locations=["LOC-01"],
        excluded_locations=["LOC-02"],
        tariffs=[Tariff(price=0.5)],
    )
    assert n.included_locations == ["LOC-01"]
    assert n.excluded_locations == ["LOC-02"]


def test_plan_cashback():
    """Test cashback field on a Plan."""
    p = Plan(
        name="Cashback Plan",
        cashback=0.05,
        networks=[Network(network_id="Test", tariffs=[Tariff(price=0.5)])],
    )
    assert p.cashback == 0.05


def test_tariff_serialization_includes_default_unit():
    """Ensure dumping model to JSON includes default 'unit' and excludes None values."""
    doc = TariffDocument(
        providers=[
            Provider(
                name="TestProvider",
                plans=[
                    Plan(
                        name="TestPlan",
                        networks=[
                            Network(
                                network_id="TestNetwork",
                                tariffs=[
                                    Tariff(type="DC", price=0.45),
                                    Tariff(type="AC", tiers=[TariffTier(price=0.5)]),
                                ],
                            )
                        ],
                    )
                ],
            )
        ]
    )

    json_str = doc.model_dump_json(exclude_none=True)
    import json

    parsed = json.loads(json_str)

    tariff_1 = parsed["providers"][0]["plans"][0]["networks"][0]["tariffs"][0]
    tariff_2_tier = parsed["providers"][0]["plans"][0]["networks"][0]["tariffs"][1][
        "tiers"
    ][0]

    assert tariff_1["unit"] == "energy"
    assert tariff_2_tier["unit"] == "energy"

    plan = parsed["providers"][0]["plans"][0]
    assert "cost" not in plan
    assert "min" not in tariff_1
