import os

import pytest
import yaml
from pydantic import ValidationError

from tariffs.model import (
    DimensionType,
    Network,
    PaymentMethod,
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
        os.path.dirname(__file__), "..", "src", "tariffs", "template.yaml"
    )
    assert os.path.exists(template_path), "Template file missing"

    with open(template_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Should not raise validation error
    doc = TariffDocument.model_validate(data)

    # Basic structural assertions
    assert len(doc.providers) > 0

    # Locate a specific plan and network to verify newly added fields like cashback
    plan_base = next(p for p in doc.providers[0].plans if p.name == "PlanName")

    # Locate a network to verify cashback, locations and time restrictions
    mobie_network = next(n for n in plan_base.networks if n.network_id == "NetworkName")
    assert mobie_network.cashback == 0.0
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


def test_tariff_thresholded_fee():
    """Tariff with thresholded fee (start_after) is valid."""
    t = Tariff(type="AC", price=0.20, unit="parking", start_after=60)
    assert t.price == 0.20
    assert t.unit == "parking"
    assert t.start_after == 60.0

    tier = TariffTier(price=0.25, unit="parking", start_after=45)
    assert tier.start_after == 45.0



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


def test_network_cashback():
    """Test cashback field on a Network."""
    n = Network(
        network_id="Test",
        cashback=0.05,
        tariffs=[Tariff(price=0.5)],
    )
    assert n.cashback == 0.05


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


def test_dimension_type_and_payment_method_enums():
    """Verify DimensionType and PaymentMethod enum validation and values."""
    assert DimensionType.ENERGY == "energy"
    assert DimensionType.TIME == "time"
    assert DimensionType.FLAT == "flat"
    assert DimensionType.PARKING == "parking"

    assert PaymentMethod.APP == "APP"

    plan = Plan(name="TestPlan", payment_methods=["APP", "RFID_CARD"], networks=[])
    assert plan.payment_methods == [PaymentMethod.APP, PaymentMethod.RFID_CARD]

    t = Tariff(price=0.5, unit="parking")
    assert t.unit == DimensionType.PARKING


def test_tariff_property_propagation_to_tiers():
    """Ensure unit and start_after propagate from parent Tariff to child TariffTiers."""
    t = Tariff(
        type="DC",
        unit="time",
        start_after=90,
        tiers=[
            TariffTier(max=100.0, price=0.20),
            TariffTier(min=100.0, price=0.25, start_after=60),
        ],
    )

    assert t.tiers[0].unit == DimensionType.TIME
    assert t.tiers[0].start_after == 90

    # Tier 2 explicitly overrode start_after to 60, but inherited unit="time"
    assert t.tiers[1].unit == DimensionType.TIME
    assert t.tiers[1].start_after == 60


def test_tariff_cannot_have_price_and_tiers():
    """Ensure specifying both price and tiers raises a ValidationError."""
    with pytest.raises(
        ValidationError, match='Cannot specify both "price" and "tiers" in a tariff'
    ):
        Tariff(
            price=0.50,
            tiers=[TariffTier(price=0.50)],
        )


def test_byoe_provider_and_plan_fields():
    """Test BYOE plan fields validation."""
    from tariffs.model import TariffPeriod

    provider = Provider(
        name="ACP Electric",
        url="https://www.acp.pt",
        updated_at="2026-08-08",
        plans=[
            Plan(
                name="2H",
                byoe=True,
                cycle="diario",
                includes_egme=True,
                includes_iec=False,
                includes_tar=False,
                activation_fee=0.15,
                renewable_energy=True,
                networks=[
                    Network(
                        network_id="MOBIE",
                        tariffs=[
                            Tariff(price=0.169, tou_period=TariffPeriod.CHEIAS),
                            Tariff(price=0.169, tou_period=TariffPeriod.VAZIO),
                        ],
                    )
                ],
            )
        ],
    )
    assert provider.plans[0].byoe is True
    assert provider.plans[0].cycle == "diario"
    assert provider.plans[0].includes_egme is True
    assert provider.plans[0].networks[0].tariffs[0].tou_period == "cheias"


def test_regulated_fees_model():
    """Test RegulatedFees and RegulatedFeesDocument models."""
    from tariffs.regulated_fees import (
        RegulatedFees,
        RegulatedFeesDocument,
        TarPeriodRate,
        TariffPeriod,
        TarVariant,
    )

    doc = RegulatedFeesDocument(
        regulated_fees=[
            RegulatedFees(
                country_code="PT",
                effective_date="2025-01-01",
                tar_variants=[
                    TarVariant(
                        voltage_level="BTE",
                        cycle="diario",
                        rates=[
                            TarPeriodRate(period=TariffPeriod.PONTA, rate=0.01),
                            TarPeriodRate(period=TariffPeriod.CHEIAS, rate=0.005),
                        ],
                    )
                ],
                iec=0.001,
                egme_connection=0.0276,
            )
        ]
    )
    assert len(doc.regulated_fees) == 1
    assert doc.regulated_fees[0].tar_variants[0].rates[0].rate == 0.01



