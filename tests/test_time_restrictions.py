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
    find_matching_cycle_schedule,
    load_time_restrictions,
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
    assert len(doc.time_restrictions_definitions) >= 6

    # Verify each definition has start_date
    for definition in doc.time_restrictions_definitions:
        assert definition.country_code == "PT"
        assert definition.start_date == "2026-01-01"


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
    vazio_hours = calculate_total_weekly_hours(vazio_restrictions)
    assert vazio_hours == 70.0

    fora_vazio_restrictions = resolve_time_restrictions(
        period=TariffPeriod.FORA_VAZIO,
        cycle=TariffCycle.DIARIO,
        schedule=TariffSchedule.BIHORARIO,
        definitions=definitions,
    )
    assert fora_vazio_restrictions is not None
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

