"""Time-of-use (TOU) cycle schedule and time restriction resolver."""

import os
from typing import Any

import yaml

from .regulated_fees import (
    TariffCycle,
    TariffCycleSchedule,
    TariffPeriod,
    TariffSchedule,
    TimeRestriction,
    TimeRestrictionsDocument,
)

DEFAULT_TIME_RESTRICTIONS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "pt", "byoe_fees", "time_restrictions.yaml"
)


def load_time_restrictions(file_path: str | None = None) -> list[TariffCycleSchedule]:
    """Load and parse time restrictions definitions from a YAML file."""
    path = file_path or DEFAULT_TIME_RESTRICTIONS_PATH
    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        return []

    doc = TimeRestrictionsDocument.model_validate(data)
    return doc.time_restrictions_definitions


def find_matching_cycle_schedule(
    definitions: list[TariffCycleSchedule],
    country_code: str | None = "PT",
    cycle: TariffCycle | str | None = None,
    schedule: TariffSchedule | str | None = None,
    effective_date: str | None = None,
    season: str | None = None,
) -> TariffCycleSchedule | None:
    """Find the most applicable TariffCycleSchedule matching country, cycle, schedule, date and season."""
    target_country = (country_code or "PT").upper()
    cycle_val = cycle.value if isinstance(cycle, TariffCycle) else (str(cycle).lower() if cycle else None)
    sched_val = schedule.value if isinstance(schedule, TariffSchedule) else (str(schedule).upper() if schedule else None)

    candidates = [
        d for d in definitions
        if d.country_code.upper() == target_country
        and (cycle_val is None or d.cycle == cycle_val or d.cycle.value == cycle_val)
        and (sched_val is None or d.schedule == sched_val or d.schedule.value == sched_val)
    ]

    if season is not None:
        season_candidates = [d for d in candidates if d.season == season.lower()]
        if season_candidates:
            candidates = season_candidates
    else:
        # If no season specified, prefer non-seasonal or first available
        non_seasonal = [d for d in candidates if d.season is None]
        if non_seasonal:
            candidates = non_seasonal

    if not candidates:
        return None

    if effective_date is not None:
        valid_candidates = []
        for c in candidates:
            if c.start_date and c.start_date > effective_date:
                continue
            if c.end_date and c.end_date < effective_date:
                continue
            valid_candidates.append(c)

        if valid_candidates:
            valid_candidates.sort(key=lambda c: c.start_date or "", reverse=True)
            return valid_candidates[0]

    # Fallback to candidate with latest start_date
    candidates.sort(key=lambda c: c.start_date or "", reverse=True)
    return candidates[0]


def resolve_time_restrictions(
    period: TariffPeriod | str,
    cycle: TariffCycle | str,
    schedule: TariffSchedule | str,
    definitions: list[TariffCycleSchedule] | None = None,
    country_code: str | None = "PT",
    effective_date: str | None = None,
    season: str | None = None,
) -> list[TimeRestriction] | None:
    """Resolve a Time-of-Use TariffPeriod into concrete TimeRestriction objects."""
    if definitions is None:
        definitions = load_time_restrictions()

    period_val = period.value if isinstance(period, TariffPeriod) else str(period).lower()
    sched_val = schedule.value if isinstance(schedule, TariffSchedule) else str(schedule).upper()

    # Normalize 2H cheias to fora_vazio
    if sched_val == "2H" and period_val == "cheias":
        period_val = "fora_vazio"

    matched = find_matching_cycle_schedule(
        definitions=definitions,
        country_code=country_code,
        cycle=cycle,
        schedule=schedule,
        effective_date=effective_date,
        season=season,
    )

    if not matched or not matched.periods:
        return None

    for p_enum, restrs in matched.periods.items():
        p_str = p_enum.value if isinstance(p_enum, TariffPeriod) else str(p_enum).lower()
        if p_str == period_val:
            return [r.model_copy() for r in restrs]

    return None


def calculate_restriction_duration_hours(restriction: TimeRestriction) -> float:
    """Calculate the weekly duration in hours for a single TimeRestriction."""
    if not restriction.start_time or not restriction.end_time:
        days_count = len(restriction.days_of_week) if restriction.days_of_week else 7
        return 24.0 * days_count

    start_h, start_m = map(int, restriction.start_time.split(":"))
    end_h, end_m = map(int, restriction.end_time.split(":"))

    start_mins = start_h * 60 + start_m
    end_mins = end_h * 60 + end_m

    if end_mins == 0 and restriction.end_time in ("00:00", "24:00") and start_mins > 0:
        end_mins = 24 * 60
    elif end_mins <= start_mins:
        # Crosses midnight (e.g. 22:00 to 08:00)
        end_mins += 24 * 60

    daily_hours = (end_mins - start_mins) / 60.0
    days_count = len(restriction.days_of_week) if restriction.days_of_week else 7
    return daily_hours * days_count


def calculate_total_weekly_hours(restrictions: list[TimeRestriction] | None) -> float:
    """Calculate the total duration in hours per week covered by a list of TimeRestrictions."""
    if not restrictions:
        return 0.0
    return sum(calculate_restriction_duration_hours(r) for r in restrictions)
