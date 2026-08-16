import os

import pytest
import yaml
from pydantic import ValidationError

from tariffs.model import (
    AppUrl,
    ContractCondition,
    DimensionType,
    DisplayText,
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

    provider = doc.providers[0]
    assert provider.app_url is not None
    assert provider.app_url.web == "https://app.provider.com"
    assert (
        provider.app_url.android
        == "https://play.google.com/store/apps/details?id=com.provider.app"
    )
    assert provider.app_url.ios == "https://apps.apple.com/app/id123456789"

    # Locate a specific plan and network to verify newly added fields
    plan_base = next(p for p in provider.plans if p.name == "PlanName")
    assert plan_base.includes_vat is True
    assert plan_base.contract_conditions == [ContractCondition.APP_ACTIVATION]
    assert plan_base.notes is not None
    assert plan_base.notes[0].language == "pt"
    assert (
        plan_base.notes[0].text
        == "Desconto válido para carregamentos na rede nacional."
    )

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
    from tariffs.model import ByoeConfig, TariffPeriod

    provider = Provider(
        name="ACP Electric",
        url="https://www.acp.pt",
        updated_at="2026-08-08",
        plans=[
            Plan(
                name="2H",
                byoe=ByoeConfig(
                    cycle="diario",
                    includes_egme=True,
                    includes_iec=False,
                    includes_tar=False,
                    activation_fee=0.15,
                    renewable_energy=True,
                ),
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
    assert provider.plans[0].is_byoe is True
    assert provider.plans[0].byoe.cycle == "diario"
    assert provider.plans[0].byoe.includes_egme is True
    assert provider.plans[0].networks[0].tariffs[0].tou_period == "cheias"

    # Test boolean shorthand
    plan_shorthand = Plan(name="Shorthand", byoe=True, networks=[])
    assert plan_shorthand.is_byoe is True
    assert plan_shorthand.byoe == ByoeConfig()

    plan_none = Plan(name="Standard", networks=[])
    assert plan_none.is_byoe is False
    assert plan_none.byoe is None


def test_regulated_fees_model():
    """Test RegulatedFees and RegulatedFeesDocument models."""
    from tariffs.regulated_fees import (
        RegulatedFees,
        RegulatedFeesDocument,
        TariffPeriod,
        TarPeriodRate,
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


def test_provider_app_url():
    """Test app_url options (web, android, ios) on Provider."""
    prov = Provider(
        name="TestProv",
        app_url=AppUrl(
            web="https://web.app",
            android="https://play.google.com/store/apps/details?id=com.app",
            ios="https://apps.apple.com/app/id123",
        ),
        plans=[],
    )
    assert prov.app_url.web == "https://web.app"
    assert (
        prov.app_url.android == "https://play.google.com/store/apps/details?id=com.app"
    )
    assert prov.app_url.ios == "https://apps.apple.com/app/id123"

    # Test string parsing
    prov_str = Provider(name="TestStr", app_url="https://simple.web.app", plans=[])
    assert prov_str.app_url.web == "https://simple.web.app"
    assert prov_str.app_url.android is None
    assert prov_str.app_url.ios is None


def test_plan_contract_conditions():
    """Test contract_conditions enum collection on Plan."""
    plan = Plan(
        name="ContractPlan",
        contract_conditions=[
            ContractCondition.ENERGY_AT_HOME,
            ContractCondition.PARTNERSHIP,
            ContractCondition.APP_ACTIVATION,
        ],
        networks=[],
    )
    assert len(plan.contract_conditions) == 3
    assert ContractCondition.ENERGY_AT_HOME in plan.contract_conditions
    assert ContractCondition.PARTNERSHIP in plan.contract_conditions
    assert ContractCondition.APP_ACTIVATION in plan.contract_conditions

    # Test alias support with strings
    plan_alias = Plan(
        name="AliasPlan",
        conditions=["ENERGY_AT_HOME", "APP_ACTIVATION"],
        networks=[],
    )
    assert plan_alias.contract_conditions == [
        ContractCondition.ENERGY_AT_HOME,
        ContractCondition.APP_ACTIVATION,
    ]


def test_plan_notes():
    """Test notes field with DisplayText objects on Plan."""
    plan = Plan(
        name="NotesPlan",
        notes=[
            DisplayText(language="pt", text="Nota em português"),
            DisplayText(language="en", text="Note in English"),
        ],
        networks=[],
    )
    assert len(plan.notes) == 2
    assert plan.notes[0].language == "pt"
    assert plan.notes[0].text == "Nota em português"
    assert plan.notes[1].language == "en"
    assert plan.notes[1].text == "Note in English"

    # Test string parsing fallback
    plan_str = Plan(name="StrNotesPlan", notes="Nota simples", networks=[])
    assert len(plan_str.notes) == 1
    assert plan_str.notes[0].language == "pt"
    assert plan_str.notes[0].text == "Nota simples"


def test_schedule_field_on_plan_and_tar_variant():
    """Test schedule field on Plan (under byoe) and TarVariant."""
    from tariffs.model import ByoeConfig
    from tariffs.regulated_fees import TariffPeriod, TarPeriodRate, TarVariant

    plan = Plan(name="TestBYOEPlan", byoe=ByoeConfig(schedule="2H"), networks=[])
    assert plan.byoe.schedule == "2H"

    variant = TarVariant(
        voltage_level="BT",
        schedule="3H",
        rates=[TarPeriodRate(period=TariffPeriod.PONTA, rate=0.28)],
    )
    assert variant.schedule == "3H"


def test_schedule_2h_tou_period_validation_and_mapping():
    """Test tou_period validation and mapping for 2H schedule."""
    from tariffs.model import ByoeConfig
    from tariffs.regulated_fees import TariffPeriod

    # 1. Cheias mapped to fora_vazio, Vazio remains vazio
    plan = Plan(
        name="2H Plan",
        byoe=ByoeConfig(schedule="2H"),
        networks=[
            Network(
                network_id="NET1",
                tariffs=[
                    Tariff(price=0.20, tou_period="cheias"),
                    Tariff(price=0.15, tou_period="vazio"),
                    Tariff(price=0.22, tou_period="fora_vazio"),
                ],
            )
        ],
    )
    assert plan.networks[0].tariffs[0].tou_period == TariffPeriod.FORA_VAZIO
    assert plan.networks[0].tariffs[1].tou_period == TariffPeriod.VAZIO
    assert plan.networks[0].tariffs[2].tou_period == TariffPeriod.FORA_VAZIO

    # 2. Case-insensitivity (CHEIAS, VAZIO, FORA_VAZIO)
    plan_upper = Plan(
        name="2H Upper Plan",
        byoe={"schedule": "2H"},
        networks=[
            Network(
                network_id="NET1",
                tariffs=[
                    Tariff(price=0.20, tou_period="CHEIAS"),
                    Tariff(price=0.15, tou_period="VAZIO"),
                    Tariff(price=0.22, tou_period="FORA_VAZIO"),
                ],
            )
        ],
    )
    assert plan_upper.networks[0].tariffs[0].tou_period == TariffPeriod.FORA_VAZIO
    assert plan_upper.networks[0].tariffs[1].tou_period == TariffPeriod.VAZIO
    assert plan_upper.networks[0].tariffs[2].tou_period == TariffPeriod.FORA_VAZIO

    # 3. Invalid tou_period for 2H (e.g. ponta) raises ValidationError
    with pytest.raises(
        ValidationError, match="Invalid tou_period 'ponta' for schedule '2H'"
    ):
        Plan(
            name="2H Invalid Plan",
            byoe=ByoeConfig(schedule="2H"),
            networks=[
                Network(
                    network_id="NET1",
                    tariffs=[
                        Tariff(price=0.30, tou_period="ponta"),
                    ],
                )
            ],
        )

    # 4. Schedule 3H allows ponta without mapping
    plan_3h = Plan(
        name="3H Plan",
        byoe=ByoeConfig(schedule="3H"),
        networks=[
            Network(
                network_id="NET1",
                tariffs=[
                    Tariff(price=0.30, tou_period="ponta"),
                    Tariff(price=0.20, tou_period="cheias"),
                    Tariff(price=0.10, tou_period="vazio"),
                ],
            )
        ],
    )
    assert plan_3h.networks[0].tariffs[0].tou_period == TariffPeriod.PONTA
    assert plan_3h.networks[0].tariffs[1].tou_period == TariffPeriod.CHEIAS
    assert plan_3h.networks[0].tariffs[2].tou_period == TariffPeriod.VAZIO
