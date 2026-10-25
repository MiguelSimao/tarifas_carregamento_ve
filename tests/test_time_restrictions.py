import os

import pytest
import yaml

from tariffs.regulated_fees import (
    TariffCycle,
    TariffCycleSchedule,
    TariffPeriod,
    TariffSchedule,
    TimeRestriction,
    TimeRestrictionsDocument,
)
from tariffs.time_restrictions import (
    calculate_total_weekly_hours,
    find_effective_and_upcoming_schedules,
    find_matching_cycle_schedule,
    find_matching_cycle_schedules,
    get_portugal_dst_dates,
    get_season_for_date,
    get_upcoming_season,
    load_time_restrictions,
    resolve_all_time_restrictions,
    resolve_time_restrictions,
)


def test_time_restrictions_yaml_validates():
    """Ensure that the data/pt/byoe_fees/time_restrictions.yaml file is valid."""
    yaml_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "pt", "byoe_fees", "time_restrictions.yaml"
    )
    assert os.path.exists(yaml_path), f"File {yaml_path} does not exist"

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    doc = TimeRestrictionsDocument.model_validate(data)
    assert len(doc.time_restrictions_definitions) >= 20

    # Verify each definition has effective_start_date and valid country_code
    for definition in doc.time_restrictions_definitions:
        assert definition.country_code in ("PT", "PT::RAA", "PT::RAM")
        assert definition.effective_start_date == "2026-01-01"


def test_ciclo_diario_2h_weekly_hours():
    """Ensure Ciclo Diário 2H has exactly 70h Vazio and 98h Fora de Vazio (total 168h)."""
    definitions = load_time_restrictions()

    vazio_restrictions = resolve_time_restrictions(
        period=TariffPeriod.VAZIO,
        cycle=TariffCycle.DIARIO,
        schedule=TariffSchedule.BIHORARIO,
        definitions=definitions,
    )
    assert vazio_restrictions is not None
    assert all(r.name == "vazio" for r in vazio_restrictions)
    vazio_hours = calculate_total_weekly_hours(vazio_restrictions)
    assert vazio_hours == 70.0

    fora_vazio_restrictions = resolve_time_restrictions(
        period=TariffPeriod.FORA_VAZIO,
        cycle=TariffCycle.DIARIO,
        schedule=TariffSchedule.BIHORARIO,
        definitions=definitions,
    )
    assert fora_vazio_restrictions is not None
    assert all(r.name == "fora_vazio" for r in fora_vazio_restrictions)
    fora_vazio_hours = calculate_total_weekly_hours(fora_vazio_restrictions)
    assert fora_vazio_hours == 98.0

    assert vazio_hours + fora_vazio_hours == 168.0


def test_ciclo_semanal_2h_weekly_hours():
    """Ensure Ciclo Semanal 2H has exactly 76h Vazio and 92h Fora de Vazio (total 168h)."""
    definitions = load_time_restrictions()

    vazio_restrictions = resolve_time_restrictions(
        period=TariffPeriod.VAZIO,
        cycle=TariffCycle.SEMANAL,
        schedule=TariffSchedule.BIHORARIO,
        definitions=definitions,
    )
    assert vazio_restrictions is not None
    vazio_hours = calculate_total_weekly_hours(vazio_restrictions)
    assert vazio_hours == 76.0

    fora_vazio_restrictions = resolve_time_restrictions(
        period=TariffPeriod.FORA_VAZIO,
        cycle=TariffCycle.SEMANAL,
        schedule=TariffSchedule.BIHORARIO,
        definitions=definitions,
    )
    assert fora_vazio_restrictions is not None
    fora_vazio_hours = calculate_total_weekly_hours(fora_vazio_restrictions)
    assert fora_vazio_hours == 92.0

    assert vazio_hours + fora_vazio_hours == 168.0


def test_ciclo_diario_3h_weekly_hours():
    """Ensure Ciclo Diário 3H (Inverno and Verão) sums to 168h with 70h Vazio."""
    definitions = load_time_restrictions()

    for season in ("inverno", "verao"):
        vazio_restrs = resolve_time_restrictions(
            period=TariffPeriod.VAZIO,
            cycle=TariffCycle.DIARIO,
            schedule=TariffSchedule.TRIHORARIO,
            season=season,
            definitions=definitions,
        )
        ponta_restrs = resolve_time_restrictions(
            period=TariffPeriod.PONTA,
            cycle=TariffCycle.DIARIO,
            schedule=TariffSchedule.TRIHORARIO,
            season=season,
            definitions=definitions,
        )
        cheias_restrs = resolve_time_restrictions(
            period=TariffPeriod.CHEIAS,
            cycle=TariffCycle.DIARIO,
            schedule=TariffSchedule.TRIHORARIO,
            season=season,
            definitions=definitions,
        )

        v_h = calculate_total_weekly_hours(vazio_restrs)
        p_h = calculate_total_weekly_hours(ponta_restrs)
        c_h = calculate_total_weekly_hours(cheias_restrs)

        assert v_h == 70.0
        assert v_h + p_h + c_h == 168.0


def test_ciclo_semanal_3h_weekly_hours():
    """Ensure Ciclo Semanal 3H (Inverno and Verão) sums to 168h with 76h Vazio."""
    definitions = load_time_restrictions()

    for season in ("inverno", "verao"):
        vazio_restrs = resolve_time_restrictions(
            period=TariffPeriod.VAZIO,
            cycle=TariffCycle.SEMANAL,
            schedule=TariffSchedule.TRIHORARIO,
            season=season,
            definitions=definitions,
        )
        ponta_restrs = resolve_time_restrictions(
            period=TariffPeriod.PONTA,
            cycle=TariffCycle.SEMANAL,
            schedule=TariffSchedule.TRIHORARIO,
            season=season,
            definitions=definitions,
        )
        cheias_restrs = resolve_time_restrictions(
            period=TariffPeriod.CHEIAS,
            cycle=TariffCycle.SEMANAL,
            schedule=TariffSchedule.TRIHORARIO,
            season=season,
            definitions=definitions,
        )

        v_h = calculate_total_weekly_hours(vazio_restrs)
        p_h = calculate_total_weekly_hours(ponta_restrs)
        c_h = calculate_total_weekly_hours(cheias_restrs)

        assert v_h == 76.0
        assert v_h + p_h + c_h == 168.0


def test_2h_cheias_maps_to_fora_vazio():
    """Ensure resolving 2H CHEIAS returns the FORA_VAZIO restrictions."""
    definitions = load_time_restrictions()

    restrs = resolve_time_restrictions(
        period=TariffPeriod.CHEIAS,
        cycle=TariffCycle.DIARIO,
        schedule=TariffSchedule.BIHORARIO,
        definitions=definitions,
    )
    assert restrs is not None
    assert len(restrs) == 1
    assert restrs[0].start_time == "08:00"
    assert restrs[0].end_time == "22:00"


def test_date_range_filtering_for_future_updates():
    """Ensure start_date and end_date correctly match or filter historical vs future definitions."""
    definitions = [
        TariffCycleSchedule(
            country_code="PT",
            start_date="2024-01-01",
            end_date="2025-12-31",
            cycle=TariffCycle.DIARIO,
            schedule=TariffSchedule.BIHORARIO,
            periods={
                TariffPeriod.VAZIO: [
                    TimeRestriction(start_time="22:00", end_time="08:00", days_of_week=[1, 2, 3, 4, 5, 6, 7])
                ]
            },
        ),
        TariffCycleSchedule(
            country_code="PT",
            start_date="2026-01-01",
            end_date=None,
            cycle=TariffCycle.DIARIO,
            schedule=TariffSchedule.BIHORARIO,
            periods={
                TariffPeriod.VAZIO: [
                    TimeRestriction(start_time="22:30", end_time="08:30", days_of_week=[1, 2, 3, 4, 5, 6, 7])
                ]
            },
        ),
    ]

    matched_old = find_matching_cycle_schedule(
        definitions,
        country_code="PT",
        cycle=TariffCycle.DIARIO,
        schedule=TariffSchedule.BIHORARIO,
        effective_date="2025-06-01",
    )
    assert matched_old is not None
    assert matched_old.start_date == "2024-01-01"
    assert matched_old.periods[TariffPeriod.VAZIO][0].start_time == "22:00"

    matched_new = find_matching_cycle_schedule(
        definitions,
        country_code="PT",
        cycle=TariffCycle.DIARIO,
        schedule=TariffSchedule.BIHORARIO,
        effective_date="2026-07-01",
    )
    assert matched_new is not None
    assert matched_new.start_date == "2026-01-01"
    assert matched_new.periods[TariffPeriod.VAZIO][0].start_time == "22:30"


def test_find_matching_cycle_schedules_returns_all_seasons():
    """Ensure find_matching_cycle_schedules returns all seasonal definitions when season is None."""
    definitions = load_time_restrictions()

    # 2H Diario is non-seasonal -> 1 schedule
    schedules_2h = find_matching_cycle_schedules(
        definitions,
        country_code="PT",
        cycle=TariffCycle.DIARIO,
        schedule=TariffSchedule.BIHORARIO,
    )
    assert len(schedules_2h) == 1
    assert schedules_2h[0].season is None

    # 3H Diario has inverno & verao -> 2 schedules
    schedules_3h = find_matching_cycle_schedules(
        definitions,
        country_code="PT",
        cycle=TariffCycle.DIARIO,
        schedule=TariffSchedule.TRIHORARIO,
    )
    assert len(schedules_3h) == 2
    seasons = {s.season for s in schedules_3h}
    assert seasons == {"inverno", "verao"}


def test_resolve_all_time_restrictions_3h_seasonal_deduplication():
    """Ensure resolve_all_time_restrictions returns 2 variants for Ponta/Cheias and 1 for Vazio."""
    definitions = load_time_restrictions()

    # Ponta has differing hours between winter and summer -> 2 unique lists
    ponta_variants = resolve_all_time_restrictions(
        period=TariffPeriod.PONTA,
        cycle=TariffCycle.DIARIO,
        schedule=TariffSchedule.TRIHORARIO,
        definitions=definitions,
    )
    assert len(ponta_variants) == 2

    # Cheias has differing hours between winter and summer -> 2 unique lists
    cheias_variants = resolve_all_time_restrictions(
        period=TariffPeriod.CHEIAS,
        cycle=TariffCycle.DIARIO,
        schedule=TariffSchedule.TRIHORARIO,
        definitions=definitions,
    )
    assert len(cheias_variants) == 2

    # Vazio has identical hours in winter and summer (22:00 to 08:00) -> 1 deduplicated list
    vazio_variants = resolve_all_time_restrictions(
        period=TariffPeriod.VAZIO,
        cycle=TariffCycle.DIARIO,
        schedule=TariffSchedule.TRIHORARIO,
        definitions=definitions,
    )
    assert len(vazio_variants) == 1
    assert len(vazio_variants[0]) == 1
    assert vazio_variants[0][0].start_time == "22:00"
    assert vazio_variants[0][0].end_time == "08:00"


def test_3h_byoe_plan_expansion_generates_seasonal_tariffs():
    """Ensure expanding a 3H BYOE plan generates seasonal tariff entries for Ponta and Cheias."""
    from tariffs.byoe_generator import expand_byoe_plan
    from tariffs.model import ByoeConfig, MobieFeeType, MobieVoltageLevel, Network, Plan
    from tariffs.regulated_fees import RegulatedFees, TarPeriodRate, TarVariant

    reg_fees = [
        RegulatedFees(
            country_code="PT",
            effective_date="2026-01-01",
            tar_variants=[
                TarVariant(
                    voltage_level="BT",
                    schedule=TariffSchedule.TRIHORARIO,
                    rates=[
                        TarPeriodRate(period=TariffPeriod.PONTA, rate=0.2807),
                        TarPeriodRate(period=TariffPeriod.CHEIAS, rate=0.0769),
                        TarPeriodRate(period=TariffPeriod.VAZIO, rate=0.0266),
                    ],
                )
            ],
            iec=0.0010,
            egme_connection=0.1088,
        )
    ]

    plan_3h = Plan(
        name="Tri-horario Plan",
        country_code="PT",
        byoe=ByoeConfig(
            start_date="2026-01-01",
            cycle="diario",
            schedule="3H",
            includes_egme=True,
            includes_iec=True,
            includes_tar=False,
            ponta=0.3000,
            cheias=0.2000,
            vazio=0.1000,
        ),
        networks=[Network(network_id="MOBIE")],
    )

    expanded = expand_byoe_plan(plan_3h, reg_fees)
    tariffs = expanded.networks[0].tariffs

    # CEME tariffs: 2 Ponta (winter + summer) + 2 Cheias (winter + summer) + 1 Vazio = 5
    ceme_tariffs = [t for t in tariffs if t.mobie_fee_type == MobieFeeType.CEME]
    assert len(ceme_tariffs) == 5

    ceme_ponta = [t for t in ceme_tariffs if t.price == 0.3000]
    assert len(ceme_ponta) == 2
    assert all(t.tou_period is None for t in ceme_ponta)
    assert all(t.time_restrictions is not None for t in ceme_ponta)
    assert all(all(r.name == "ponta" for r in t.time_restrictions) for t in ceme_ponta)

    ceme_cheias = [t for t in ceme_tariffs if t.price == 0.2000]
    assert len(ceme_cheias) == 2
    assert all(all(r.name == "cheias" for r in t.time_restrictions) for t in ceme_cheias)

    ceme_vazio = [t for t in ceme_tariffs if t.price == 0.1000]
    assert len(ceme_vazio) == 1
    assert all(all(r.name == "vazio" for r in t.time_restrictions) for t in ceme_vazio)

    # TAR tariffs: 2 Ponta + 2 Cheias + 1 Vazio = 5
    tar_tariffs = [t for t in tariffs if t.mobie_fee_type == MobieFeeType.TAR]
    assert len(tar_tariffs) == 5

    tar_ponta = [t for t in tar_tariffs if t.price == 0.2807]
    assert len(tar_ponta) == 2
    assert all(t.tou_period is None for t in tar_ponta)
    assert all(all(r.name == "ponta" for r in t.time_restrictions) for t in tar_ponta)

    tar_cheias = [t for t in tar_tariffs if t.price == 0.0769]
    assert len(tar_cheias) == 2
    assert all(all(r.name == "cheias" for r in t.time_restrictions) for t in tar_cheias)

    tar_vazio = [t for t in tar_tariffs if t.price == 0.0266]
    assert len(tar_vazio) == 1
    assert all(all(r.name == "vazio" for r in t.time_restrictions) for t in tar_vazio)


def test_portugal_dst_dates_calculation():
    """Ensure Portugal DST dates correctly calculate last Sunday of March and October."""
    import datetime

    s_start_2026, w_start_2026 = get_portugal_dst_dates(2026)
    assert s_start_2026 == datetime.date(2026, 3, 29)
    assert w_start_2026 == datetime.date(2026, 10, 25)

    s_start_2027, w_start_2027 = get_portugal_dst_dates(2027)
    assert s_start_2027 == datetime.date(2027, 3, 28)
    assert w_start_2027 == datetime.date(2027, 10, 31)


def test_get_season_for_date():
    """Ensure get_season_for_date correctly identifies summer and winter in Portugal."""
    assert get_season_for_date("2026-08-16") == "verao"
    assert get_season_for_date("2026-01-15") == "inverno"
    assert get_season_for_date("2026-03-28") == "inverno"
    assert get_season_for_date("2026-03-29") == "verao"
    assert get_season_for_date("2026-10-24") == "verao"
    assert get_season_for_date("2026-10-25") == "inverno"

    assert get_upcoming_season("verao") == "inverno"
    assert get_upcoming_season("inverno") == "verao"


def test_find_effective_and_upcoming_schedules_order():
    """Ensure schedules for 'today' (reference_date) are first, and upcoming season/regulation is second."""
    definitions = load_time_restrictions()

    # When reference_date is in summer (August 2026)
    schedules_summer = find_effective_and_upcoming_schedules(
        definitions=definitions,
        country_code="PT",
        cycle=TariffCycle.DIARIO,
        schedule=TariffSchedule.TRIHORARIO,
        reference_date="2026-08-16",
    )
    assert len(schedules_summer) == 2
    assert schedules_summer[0].season == "verao"   # Today's active season
    assert schedules_summer[1].season == "inverno" # Upcoming season

    # When reference_date is in winter (January 2026)
    schedules_winter = find_effective_and_upcoming_schedules(
        definitions=definitions,
        country_code="PT",
        cycle=TariffCycle.DIARIO,
        schedule=TariffSchedule.TRIHORARIO,
        reference_date="2026-01-15",
    )
    assert len(schedules_winter) == 2
    assert schedules_winter[0].season == "inverno" # Today's active season
    assert schedules_winter[1].season == "verao"   # Upcoming season


def test_find_effective_and_upcoming_schedules_with_future_changeover():
    """Ensure upcoming regulation periods starting after reference_date are included."""
    definitions = [
        TariffCycleSchedule(
            country_code="PT",
            start_date="2026-01-01",
            end_date=None,
            cycle=TariffCycle.DIARIO,
            schedule=TariffSchedule.BIHORARIO,
            periods={
                TariffPeriod.VAZIO: [
                    TimeRestriction(start_time="22:00", end_time="08:00", days_of_week=[1, 2, 3, 4, 5, 6, 7])
                ]
            },
        ),
        TariffCycleSchedule(
            country_code="PT",
            start_date="2027-01-01",
            end_date=None,
            cycle=TariffCycle.DIARIO,
            schedule=TariffSchedule.BIHORARIO,
            periods={
                TariffPeriod.VAZIO: [
                    TimeRestriction(start_time="23:00", end_time="07:00", days_of_week=[1, 2, 3, 4, 5, 6, 7])
                ]
            },
        ),
    ]

    matched = find_effective_and_upcoming_schedules(
        definitions=definitions,
        country_code="PT",
        cycle=TariffCycle.DIARIO,
        schedule=TariffSchedule.BIHORARIO,
        reference_date="2026-08-16",
    )
    assert len(matched) == 2
    assert matched[0].start_date == "2026-01-01"  # Active today
    assert matched[1].start_date == "2027-01-01"  # Upcoming regulation changeover


def test_raa_time_restrictions_weekly_hours():
    """Ensure RAA (Azores) time restrictions sum to 168h across all cycles and schedules."""
    definitions = load_time_restrictions()

    # 1. 2H Diário
    vazio_diario = resolve_time_restrictions(
        period=TariffPeriod.VAZIO,
        cycle=TariffCycle.DIARIO,
        schedule=TariffSchedule.BIHORARIO,
        country_code="PT::RAA",
        definitions=definitions,
    )
    assert vazio_diario is not None
    assert calculate_total_weekly_hours(vazio_diario) == 70.0
    fora_vazio_diario = resolve_time_restrictions(
        period=TariffPeriod.FORA_VAZIO,
        cycle=TariffCycle.DIARIO,
        schedule=TariffSchedule.BIHORARIO,
        country_code="PT::RAA",
        definitions=definitions,
    )
    assert fora_vazio_diario is not None
    assert calculate_total_weekly_hours(fora_vazio_diario) == 98.0

    # 2. 2H Semanal (Inverno & Verão)
    for season in ("inverno", "verao"):
        vazio_sem = resolve_time_restrictions(
            period=TariffPeriod.VAZIO,
            cycle=TariffCycle.SEMANAL,
            schedule=TariffSchedule.BIHORARIO,
            country_code="PT::RAA",
            season=season,
            definitions=definitions,
        )
        fora_vazio_sem = resolve_time_restrictions(
            period=TariffPeriod.FORA_VAZIO,
            cycle=TariffCycle.SEMANAL,
            schedule=TariffSchedule.BIHORARIO,
            country_code="PT::RAA",
            season=season,
            definitions=definitions,
        )
        assert vazio_sem is not None and fora_vazio_sem is not None
        v_h = calculate_total_weekly_hours(vazio_sem)
        fv_h = calculate_total_weekly_hours(fora_vazio_sem)
        assert v_h == 76.0
        assert fv_h == 92.0
        assert v_h + fv_h == 168.0

    # 3. 3H Diário (Inverno & Verão)
    for season in ("inverno", "verao"):
        vazio = resolve_time_restrictions(
            period=TariffPeriod.VAZIO,
            cycle=TariffCycle.DIARIO,
            schedule=TariffSchedule.TRIHORARIO,
            country_code="PT::RAA",
            season=season,
            definitions=definitions,
        )
        ponta = resolve_time_restrictions(
            period=TariffPeriod.PONTA,
            cycle=TariffCycle.DIARIO,
            schedule=TariffSchedule.TRIHORARIO,
            country_code="PT::RAA",
            season=season,
            definitions=definitions,
        )
        cheias = resolve_time_restrictions(
            period=TariffPeriod.CHEIAS,
            cycle=TariffCycle.DIARIO,
            schedule=TariffSchedule.TRIHORARIO,
            country_code="PT::RAA",
            season=season,
            definitions=definitions,
        )
        v_h = calculate_total_weekly_hours(vazio)
        p_h = calculate_total_weekly_hours(ponta)
        c_h = calculate_total_weekly_hours(cheias)
        assert v_h == 70.0
        assert p_h == 28.0
        assert c_h == 70.0
        assert v_h + p_h + c_h == 168.0

    # 4. 3H Semanal (Inverno: Ponta 15h, Cheias 77h; Verão: Ponta 25h, Cheias 67h)
    for season, expected_ponta, expected_cheias in [("inverno", 15.0, 77.0), ("verao", 25.0, 67.0)]:
        vazio = resolve_time_restrictions(
            period=TariffPeriod.VAZIO,
            cycle=TariffCycle.SEMANAL,
            schedule=TariffSchedule.TRIHORARIO,
            country_code="PT::RAA",
            season=season,
            definitions=definitions,
        )
        ponta = resolve_time_restrictions(
            period=TariffPeriod.PONTA,
            cycle=TariffCycle.SEMANAL,
            schedule=TariffSchedule.TRIHORARIO,
            country_code="PT::RAA",
            season=season,
            definitions=definitions,
        )
        cheias = resolve_time_restrictions(
            period=TariffPeriod.CHEIAS,
            cycle=TariffCycle.SEMANAL,
            schedule=TariffSchedule.TRIHORARIO,
            country_code="PT::RAA",
            season=season,
            definitions=definitions,
        )
        v_h = calculate_total_weekly_hours(vazio)
        p_h = calculate_total_weekly_hours(ponta)
        c_h = calculate_total_weekly_hours(cheias)
        assert v_h == 76.0
        assert p_h == expected_ponta
        assert c_h == expected_cheias
        assert v_h + p_h + c_h == 168.0


def test_ram_time_restrictions_weekly_hours():
    """Ensure RAM (Madeira) time restrictions sum to 168h across all cycles and schedules."""
    definitions = load_time_restrictions()

    # 1. 2H Diário (Vazio: 23:00 to 09:00 -> 70h, Fora de Vazio: 09:00 to 23:00 -> 98h)
    vazio_diario = resolve_time_restrictions(
        period=TariffPeriod.VAZIO,
        cycle=TariffCycle.DIARIO,
        schedule=TariffSchedule.BIHORARIO,
        country_code="PT::RAM",
        definitions=definitions,
    )
    assert vazio_diario is not None
    assert calculate_total_weekly_hours(vazio_diario) == 70.0
    fora_vazio_diario = resolve_time_restrictions(
        period=TariffPeriod.FORA_VAZIO,
        cycle=TariffCycle.DIARIO,
        schedule=TariffSchedule.BIHORARIO,
        country_code="PT::RAM",
        definitions=definitions,
    )
    assert fora_vazio_diario is not None
    assert calculate_total_weekly_hours(fora_vazio_diario) == 98.0

    # 2. 2H Semanal (Inverno & Verão)
    for season in ("inverno", "verao"):
        vazio_sem = resolve_time_restrictions(
            period=TariffPeriod.VAZIO,
            cycle=TariffCycle.SEMANAL,
            schedule=TariffSchedule.BIHORARIO,
            country_code="PT::RAM",
            season=season,
            definitions=definitions,
        )
        fora_vazio_sem = resolve_time_restrictions(
            period=TariffPeriod.FORA_VAZIO,
            cycle=TariffCycle.SEMANAL,
            schedule=TariffSchedule.BIHORARIO,
            country_code="PT::RAM",
            season=season,
            definitions=definitions,
        )
        assert vazio_sem is not None and fora_vazio_sem is not None
        v_h = calculate_total_weekly_hours(vazio_sem)
        fv_h = calculate_total_weekly_hours(fora_vazio_sem)
        assert v_h == 76.0
        assert fv_h == 92.0
        assert v_h + fv_h == 168.0

    # 3. 3H Diário (Inverno & Verão)
    for season in ("inverno", "verao"):
        vazio = resolve_time_restrictions(
            period=TariffPeriod.VAZIO,
            cycle=TariffCycle.DIARIO,
            schedule=TariffSchedule.TRIHORARIO,
            country_code="PT::RAM",
            season=season,
            definitions=definitions,
        )
        ponta = resolve_time_restrictions(
            period=TariffPeriod.PONTA,
            cycle=TariffCycle.DIARIO,
            schedule=TariffSchedule.TRIHORARIO,
            country_code="PT::RAM",
            season=season,
            definitions=definitions,
        )
        cheias = resolve_time_restrictions(
            period=TariffPeriod.CHEIAS,
            cycle=TariffCycle.DIARIO,
            schedule=TariffSchedule.TRIHORARIO,
            country_code="PT::RAM",
            season=season,
            definitions=definitions,
        )
        v_h = calculate_total_weekly_hours(vazio)
        p_h = calculate_total_weekly_hours(ponta)
        c_h = calculate_total_weekly_hours(cheias)
        assert v_h == 70.0
        assert p_h == 28.0
        assert c_h == 70.0
        assert v_h + p_h + c_h == 168.0

    # 4. 3H Semanal (Inverno: Ponta 15h, Cheias 77h; Verão: Ponta 25h, Cheias 67h)
    for season, expected_ponta, expected_cheias in [("inverno", 15.0, 77.0), ("verao", 25.0, 67.0)]:
        vazio = resolve_time_restrictions(
            period=TariffPeriod.VAZIO,
            cycle=TariffCycle.SEMANAL,
            schedule=TariffSchedule.TRIHORARIO,
            country_code="PT::RAM",
            season=season,
            definitions=definitions,
        )
        ponta = resolve_time_restrictions(
            period=TariffPeriod.PONTA,
            cycle=TariffCycle.SEMANAL,
            schedule=TariffSchedule.TRIHORARIO,
            country_code="PT::RAM",
            season=season,
            definitions=definitions,
        )
        cheias = resolve_time_restrictions(
            period=TariffPeriod.CHEIAS,
            cycle=TariffCycle.SEMANAL,
            schedule=TariffSchedule.TRIHORARIO,
            country_code="PT::RAM",
            season=season,
            definitions=definitions,
        )
        v_h = calculate_total_weekly_hours(vazio)
        p_h = calculate_total_weekly_hours(ponta)
        c_h = calculate_total_weekly_hours(cheias)
        assert v_h == 76.0
        assert p_h == expected_ponta
        assert c_h == expected_cheias
        assert v_h + p_h + c_h == 168.0


def test_option_a_regulation_document_structure():
    """Ensure RegulationTimeRestrictions correctly groups schedules by country_code and effective_start_date."""
    yaml_path = os.path.join(
        os.path.dirname(__file__), "..", "data", "pt", "byoe_fees", "time_restrictions.yaml"
    )
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    doc = TimeRestrictionsDocument.model_validate(data)
    assert len(doc.time_restrictions) == 3

    pt_reg = next(r for r in doc.time_restrictions if r.country_code == "PT")
    assert pt_reg.effective_start_date == "2026-01-01"
    assert len(pt_reg.schedules) == 6

    raa_reg = next(r for r in doc.time_restrictions if r.country_code == "PT::RAA")
    assert raa_reg.effective_start_date == "2026-01-01"
    assert len(raa_reg.schedules) == 7

    ram_reg = next(r for r in doc.time_restrictions if r.country_code == "PT::RAM")
    assert ram_reg.effective_start_date == "2026-01-01"
    assert len(ram_reg.schedules) == 7


def test_seasonal_dates_and_cycle_aware_resolution():
    """Ensure seasonal dates and cycle-aware get_season_for_date correctly resolve seasons."""
    # Continental / Island Daily: DST transition
    assert get_season_for_date("2026-01-15", country_code="PT") == "inverno"
    assert get_season_for_date("2026-05-15", country_code="PT") == "verao"
    assert get_season_for_date("2026-08-16", country_code="PT") == "verao"
    assert get_season_for_date("2026-11-15", country_code="PT") == "inverno"

    # Island Weekly: fixed calendar (June 1 to October 31 = summer)
    assert get_season_for_date("2026-05-15", country_code="PT::RAA", cycle=TariffCycle.SEMANAL) == "inverno"
    assert get_season_for_date("2026-06-01", country_code="PT::RAA", cycle=TariffCycle.SEMANAL) == "verao"
    assert get_season_for_date("2026-08-16", country_code="PT::RAA", cycle=TariffCycle.SEMANAL) == "verao"
    assert get_season_for_date("2026-10-31", country_code="PT::RAA", cycle=TariffCycle.SEMANAL) == "verao"
    assert get_season_for_date("2026-11-01", country_code="PT::RAA", cycle=TariffCycle.SEMANAL) == "inverno"





