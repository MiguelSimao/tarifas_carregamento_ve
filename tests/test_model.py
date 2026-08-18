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
    tr = TimeRestriction(
        name="fora_vazio", start_time="08:00", end_time="20:00", days_of_week=[6, 7]
    )
    assert tr.name == "fora_vazio"
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


def test_mobie_voltage_level_and_mobie_fee_type():
    """Test MobieVoltageLevel and MobieFeeType typed enums on Tariff."""
    from tariffs.model import MobieFeeType, MobieVoltageLevel

    t = Tariff(
        price=0.25,
        unit="energy",
        mobie_fee_type=MobieFeeType.CEME,
        mobie_voltage_level=MobieVoltageLevel.BT,
    )
    assert t.mobie_fee_type == MobieFeeType.CEME
    assert t.mobie_fee_type == "CEME"
    assert t.mobie_voltage_level == MobieVoltageLevel.BT
    assert t.mobie_voltage_level == "BT"

    # String input parsed to enum
    t2 = Tariff(
        price=0.10,
        unit="flat",
        mobie_fee_type="EGME",
        mobie_voltage_level="MT",
    )
    assert t2.mobie_fee_type == MobieFeeType.EGME
    assert t2.mobie_voltage_level == MobieVoltageLevel.MT

    # MobieFeeType enum values
    assert MobieFeeType.CEME == "CEME"
    assert MobieFeeType.EGME == "EGME"
    assert MobieFeeType.TAR == "TAR"
    assert MobieFeeType.IEC == "IEC"


def test_mobie_fee_type_only_allowed_in_byoe_plans():
    """Test that mobie_fee_type is rejected in standard plans and allowed in BYOE plans."""
    from tariffs.model import ByoeConfig, MobieFeeType, Network, Plan, Tariff

    # Standard non-BYOE plan should reject mobie_fee_type
    with pytest.raises(ValidationError, match="not a BYOE plan, but defines tariff with mobie_fee_type"):
        Plan(
            name="Standard Plan",
            networks=[
                Network(
                    network_id="MOBIE",
                    tariffs=[
                        Tariff(
                            price=0.25,
                            unit="energy",
                            mobie_fee_type=MobieFeeType.CEME,
                        )
                    ],
                )
            ],
        )

    # BYOE plan allows mobie_fee_type
    byoe_plan = Plan(
        name="BYOE Plan",
        byoe=ByoeConfig(),
        networks=[
            Network(
                network_id="MOBIE",
                tariffs=[
                    Tariff(
                        price=0.25,
                        unit="energy",
                        mobie_fee_type=MobieFeeType.CEME,
                    )
                ],
            )
        ],
    )
    assert byoe_plan.networks[0].tariffs[0].mobie_fee_type == MobieFeeType.CEME


def test_byoe_rates_and_start_date_validation():
    """Test ByoeConfig rate fields, start_date and schedule validations."""
    from tariffs.model import ByoeConfig, TariffSchedule

    byoe_2h = ByoeConfig(
        start_date="2026-07-01",
        schedule=TariffSchedule.BIHORARIO,
        cheias=0.1690,
        vazio=0.1690,
    )
    assert byoe_2h.start_date == "2026-07-01"
    assert byoe_2h.vazio == 0.1690
    assert byoe_2h.cheias is None  # mapped to fora_vazio and unset
    assert byoe_2h.fora_vazio == 0.1690  # mapped from cheias

    # 2H rejecting ponta
    with pytest.raises(ValidationError, match="Schedule '2H' does not support 'ponta' rate"):
        ByoeConfig(
            schedule=TariffSchedule.BIHORARIO,
            ponta=0.25,
            vazio=0.10,
        )

    # 3H accepting ponta, cheias, vazio
    byoe_3h = ByoeConfig(
        start_date="2026-01-01",
        schedule=TariffSchedule.TRIHORARIO,
        ponta=0.28,
        cheias=0.18,
        vazio=0.12,
    )
    assert byoe_3h.ponta == 0.28
    assert byoe_3h.cheias == 0.18
    assert byoe_3h.vazio == 0.12

    # 1H rejecting ponta
    with pytest.raises(ValidationError, match="Schedule '1H' does not support 'ponta' rate"):
        ByoeConfig(
            schedule=TariffSchedule.SIMPLES,
            ponta=0.25,
            all_day=0.20,
        )

    # 1H rejecting conflicting different rates
    with pytest.raises(ValidationError, match="Schedule '1H' requires a single rate"):
        ByoeConfig(
            schedule=TariffSchedule.SIMPLES,
            cheias=0.2678,
            vazio=0.2000,
        )

    # 1H accepting all_day directly
    byoe_1h = ByoeConfig(
        start_date="2026-07-01",
        schedule=TariffSchedule.SIMPLES,
        all_day=0.2678,
    )
    assert byoe_1h.schedule == TariffSchedule.SIMPLES
    assert byoe_1h.all_day == 0.2678

    # 1H auto-normalizing equal cheias/vazio to all_day
    byoe_1h_norm = ByoeConfig(
        start_date="2026-07-01",
        schedule=TariffSchedule.SIMPLES,
        cheias=0.2678,
        vazio=0.2678,
    )
    assert byoe_1h_norm.all_day == 0.2678
    assert byoe_1h_norm.cheias is None
    assert byoe_1h_norm.vazio is None


def test_byoe_plan_expansion():
    """Test expanding a BYOE plan into concrete network tariffs."""
    from tariffs.byoe_generator import expand_byoe_plan
    from tariffs.model import ByoeConfig, MobieVoltageLevel, Plan, TariffPeriod
    from tariffs.regulated_fees import RegulatedFees, TarPeriodRate, TarVariant

    regulated_fees = [
        RegulatedFees(
            country_code="PT",
            effective_date="2026-01-01",
            tar_variants=[
                TarVariant(
                    voltage_level="MT",
                    schedule="2H",
                    rates=[
                        TarPeriodRate(period=TariffPeriod.CHEIAS, rate=0.0812),
                        TarPeriodRate(period=TariffPeriod.VAZIO, rate=0.0157),
                    ],
                ),
                TarVariant(
                    voltage_level="BT",
                    schedule="2H",
                    rates=[
                        TarPeriodRate(period=TariffPeriod.CHEIAS, rate=0.1192),
                        TarPeriodRate(period=TariffPeriod.VAZIO, rate=0.0266),
                    ],
                ),
            ],
            iec=0.0010,
            egme_connection=0.1088,
        )
    ]

    plan = Plan(
        name="ACP CEME Base",
        country_code="PT",
        byoe=ByoeConfig(
            start_date="2026-07-01",
            cycle="diario",
            schedule="2H",
            includes_egme=True,
            includes_iec=False,
            includes_tar=False,
            activation_fee=0.15,
            cheias=0.1690,
            vazio=0.1690,
        ),
        networks=[
            Network(
                network_id="MOBIE",
                tariffs=[Tariff(type="AC", byoe=True)],
            )
        ],
    )

    expanded = expand_byoe_plan(plan, regulated_fees)
    assert len(expanded.networks) == 1
    tariffs = expanded.networks[0].tariffs
    # 1 flat fee + 1 IEC energy rate + 1 CEME energy rate (no tou_period since rates are equal) + 4 TAR energy rates (2 for MT, 2 for BT)
    assert len(tariffs) == 7

    flat = next(t for t in tariffs if t.unit == "flat")
    assert flat.price == 0.15
    assert flat.mobie_fee_type is None
    assert flat.type == "AC"

    from tariffs.model import MobieFeeType

    # IEC energy tariff
    iec_tariff = next(t for t in tariffs if t.mobie_fee_type == MobieFeeType.IEC)
    assert iec_tariff.price == 0.0010
    assert iec_tariff.unit == "energy"
    assert iec_tariff.type == "AC"

    # CEME energy tariff (pure base rate 0.1690)
    ceme_tariff = next(t for t in tariffs if t.mobie_fee_type == MobieFeeType.CEME)
    assert ceme_tariff.price == 0.1690
    assert ceme_tariff.type == "AC"
    assert ceme_tariff.tou_period is None  # no TOU constraint since all rates are identical

    # TAR energy tariffs
    bt_fora_vazio = next(
        t for t in tariffs
        if t.mobie_fee_type == MobieFeeType.TAR
        and t.mobie_voltage_level == MobieVoltageLevel.BT
        and t.price == 0.1192
    )
    assert bt_fora_vazio.tou_period is None
    assert bt_fora_vazio.type == "AC"
    assert bt_fora_vazio.time_restrictions is not None
    assert len(bt_fora_vazio.time_restrictions) == 1
    assert bt_fora_vazio.time_restrictions[0].name == "fora_vazio"
    assert bt_fora_vazio.time_restrictions[0].start_time == "08:00"
    assert bt_fora_vazio.time_restrictions[0].end_time == "22:00"

    bt_vazio = next(
        t for t in tariffs
        if t.mobie_fee_type == MobieFeeType.TAR
        and t.mobie_voltage_level == MobieVoltageLevel.BT
        and t.price == 0.0266
    )
    assert bt_vazio.tou_period is None
    assert bt_vazio.type == "AC"
    assert bt_vazio.time_restrictions is not None
    assert len(bt_vazio.time_restrictions) == 1
    assert bt_vazio.time_restrictions[0].name == "vazio"
    assert bt_vazio.time_restrictions[0].start_time == "22:00"
    assert bt_vazio.time_restrictions[0].end_time == "08:00"

    # Test plan with differing TOU rates (vazio != fora_vazio) -> CEME tariffs should have time_restrictions
    plan_differing_rates = Plan(
        name="Different Rates CEME",
        country_code="PT",
        byoe=ByoeConfig(
            start_date="2026-07-01",
            cycle="diario",
            schedule="2H",
            includes_egme=True,
            includes_iec=True,
            includes_tar=False,
            cheias=0.2000,
            vazio=0.1000,
        ),
        networks=[Network(network_id="MOBIE")],
    )
    expanded_diff = expand_byoe_plan(plan_differing_rates, regulated_fees)
    tariffs_diff = expanded_diff.networks[0].tariffs
    # 2 CEME rates + 4 TAR rates = 6 (no IEC since includes_iec=True)
    assert len(tariffs_diff) == 6
    assert not any(t.mobie_fee_type == MobieFeeType.IEC for t in tariffs_diff)
    ceme_vazio = next(
        t for t in tariffs_diff
        if t.mobie_fee_type == MobieFeeType.CEME and t.price == 0.1000
    )
    assert ceme_vazio.tou_period is None
    assert ceme_vazio.time_restrictions is not None
    assert ceme_vazio.time_restrictions[0].name == "vazio"
    assert ceme_vazio.time_restrictions[0].start_time == "22:00"
    assert ceme_vazio.time_restrictions[0].end_time == "08:00"

    ceme_fora_vazio = next(
        t for t in tariffs_diff
        if t.mobie_fee_type == MobieFeeType.CEME and t.price == 0.2000
    )
    assert ceme_fora_vazio.tou_period is None
    assert ceme_fora_vazio.time_restrictions is not None
    assert ceme_fora_vazio.time_restrictions[0].name == "fora_vazio"
    assert ceme_fora_vazio.time_restrictions[0].start_time == "08:00"
    assert ceme_fora_vazio.time_restrictions[0].end_time == "22:00"

    # Test plan with includes_egme=False generating EGME fee
    plan_no_egme = Plan(
        name="Atlante CEME",
        country_code="PT",
        byoe=ByoeConfig(
            start_date="2026-01-01",
            cycle="semanal",
            schedule="2H",
            includes_egme=False,
            includes_iec=False,
            includes_tar=False,
            activation_fee=0.0,
            cheias=0.0976,
            vazio=0.0976,
        ),
        networks=[
            Network(
                network_id="MOBIE",
                tariffs=[Tariff(max=43, byoe=True)],
            )
        ],
    )
    expanded_no_egme = expand_byoe_plan(plan_no_egme, regulated_fees)
    tariffs_no_egme = expanded_no_egme.networks[0].tariffs
    # 1 EGME flat fee + 1 IEC energy rate + 1 CEME energy rate + 2 TAR BT + 2 TAR MT = 7 (all with max: 43)
    assert len(tariffs_no_egme) == 7
    assert all(t.max == 43.0 for t in tariffs_no_egme)
    assert any(t.mobie_voltage_level == MobieVoltageLevel.MT for t in tariffs_no_egme)
    assert any(t.mobie_voltage_level == MobieVoltageLevel.BT for t in tariffs_no_egme)
    egme_fee = next(t for t in tariffs_no_egme if t.mobie_fee_type == MobieFeeType.EGME)
    assert egme_fee.price == 0.1088
    assert egme_fee.unit == "flat"
    assert egme_fee.max == 43.0
    iec_fee = next(t for t in tariffs_no_egme if t.mobie_fee_type == MobieFeeType.IEC)
    assert iec_fee.price == 0.0010
    assert iec_fee.unit == "energy"
    assert iec_fee.max == 43.0


def test_byoe_placeholder_tariff_validation():
    """Test Tariff byoe placeholder validation."""
    # Placeholder tariff without price or tiers is valid
    t_ph = Tariff(max=43, byoe=True)
    assert t_ph.is_byoe_placeholder is True
    assert t_ph.max == 43.0
    assert t_ph.price is None

    # Normal tariff without price, tiers, or byoe raises error
    with pytest.raises(ValidationError, match='Either "price" or "tiers" must be provided'):
        Tariff(max=43)

    # Standard plan rejects byoe placeholder tariff
    with pytest.raises(ValidationError, match="defines tariff with byoe placeholder"):
        Plan(
            name="Standard Plan",
            networks=[
                Network(
                    network_id="MOBIE",
                    tariffs=[Tariff(max=43, byoe=True)],
                )
            ],
        )


def test_byoe_config_includes_vat_default():
    """Test ByoeConfig includes_vat defaults to False."""
    from tariffs.model import ByoeConfig

    cfg = ByoeConfig(start_date="2026-01-01")
    assert cfg.includes_vat is False

    cfg_true = ByoeConfig(start_date="2026-01-01", includes_vat=True)
    assert cfg_true.includes_vat is True

    cfg_alias = ByoeConfig(start_date="2026-01-01", vat_included=True)
    assert cfg_alias.includes_vat is True


def test_byoe_multi_placeholder_expansion():
    """Test expanding multiple placeholder tariffs with explicit voltage levels."""
    from tariffs.byoe_generator import expand_byoe_plan
    from tariffs.model import ByoeConfig, MobieFeeType, MobieVoltageLevel, Network, Plan, Tariff
    from tariffs.regulated_fees import RegulatedFees, TariffPeriod, TarPeriodRate, TarVariant

    regulated_fees = [
        RegulatedFees(
            country_code="PT",
            effective_date="2026-01-01",
            tar_variants=[
                TarVariant(
                    voltage_level="MT",
                    schedule="2H",
                    rates=[
                        TarPeriodRate(period=TariffPeriod.CHEIAS, rate=0.0812),
                        TarPeriodRate(period=TariffPeriod.VAZIO, rate=0.0157),
                    ],
                ),
                TarVariant(
                    voltage_level="BT",
                    schedule="2H",
                    rates=[
                        TarPeriodRate(period=TariffPeriod.CHEIAS, rate=0.1192),
                        TarPeriodRate(period=TariffPeriod.VAZIO, rate=0.0266),
                    ],
                ),
            ],
            iec=0.0010,
            egme_connection=0.1088,
        )
    ]

    plan = Plan(
        name="Tiered CEME",
        country_code="PT",
        byoe=ByoeConfig(
            start_date="2026-01-01",
            schedule="2H",
            cheias=0.1000,
            vazio=0.1000,
        ),
        networks=[
            Network(
                network_id="MOBIE",
                tariffs=[
                    Tariff(type="AC", max=43, mobie_voltage_level=MobieVoltageLevel.BT, byoe=True),
                    Tariff(type="DC", min=43, mobie_voltage_level=MobieVoltageLevel.MT, byoe=True),
                ],
            )
        ],
    )

    expanded = expand_byoe_plan(plan, regulated_fees)
    tariffs = expanded.networks[0].tariffs

    ac_tariffs = [t for t in tariffs if t.type == "AC"]
    dc_tariffs = [t for t in tariffs if t.type == "DC"]

    # AC (BT only): EGME + IEC + CEME + 2 TAR BT = 5
    assert len(ac_tariffs) == 5
    assert all(t.max == 43.0 for t in ac_tariffs)
    assert all(t.min is None for t in ac_tariffs)
    assert all(t.mobie_voltage_level != MobieVoltageLevel.MT for t in ac_tariffs)

    # DC (MT only): EGME + IEC + CEME + 2 TAR MT = 5
    assert len(dc_tariffs) == 5
    assert all(t.min == 43.0 for t in dc_tariffs)
    assert all(t.max is None for t in dc_tariffs)
    assert all(t.mobie_voltage_level != MobieVoltageLevel.BT for t in dc_tariffs)



