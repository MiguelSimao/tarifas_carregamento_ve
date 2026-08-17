import datetime
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


def get_portugal_dst_dates(year: int) -> tuple[datetime.date, datetime.date]:
    """Calculate the Daylight Saving Time (DST) transition dates for Portugal (EU standard).
    
    Summer (Verão) starts at 01:00 UTC on the last Sunday of March.
    Winter (Inverno) starts at 01:00 UTC on the last Sunday of October.
    
    Returns:
        (summer_start_date, winter_start_date)
    """
    march_31 = datetime.date(year, 3, 31)
    summer_start = march_31 - datetime.timedelta(days=(march_31.weekday() + 1) % 7)

    oct_31 = datetime.date(year, 10, 31)
    winter_start = oct_31 - datetime.timedelta(days=(oct_31.weekday() + 1) % 7)

    return summer_start, winter_start


def get_season_for_date(
    target_date: str | datetime.date | None = None,
    country_code: str = "PT",
) -> str:
    """Determine the active season ('verao' or 'inverno') for a given date in Portugal."""
    if target_date is None:
        d = datetime.date.today()
    elif isinstance(target_date, str):
        d = datetime.date.fromisoformat(target_date)
    else:
        d = target_date

    country = (country_code or "PT").upper()
    if country == "PT":
        summer_start, winter_start = get_portugal_dst_dates(d.year)
        if summer_start <= d < winter_start:
            return "verao"
        return "inverno"

    summer_start, winter_start = get_portugal_dst_dates(d.year)
    if summer_start <= d < winter_start:
        return "verao"
    return "inverno"


def get_upcoming_season(current_season: str) -> str:
    """Get the upcoming season given the current season."""
    return "inverno" if current_season.lower() == "verao" else "verao"


def find_effective_and_upcoming_schedules(
    definitions: list[TariffCycleSchedule],
    country_code: str | None = "PT",
    cycle: TariffCycle | str | None = None,
    schedule: TariffSchedule | str | None = None,
    reference_date: str | None = None,
) -> list[TariffCycleSchedule]:
    """Find schedule definitions for 'today' (reference_date) and the upcoming season/regulation period.
    
    Returns an ordered list of TariffCycleSchedule objects:
    1. Schedule(s) active on reference_date (today), selecting the current season if seasonal.
    2. Upcoming season schedule (if seasonal) or next regulation changeover schedule.
    """
    ref_d_str = reference_date or datetime.date.today().isoformat()
    target_country = (country_code or "PT").upper()
    cycle_val = cycle.value if isinstance(cycle, TariffCycle) else (str(cycle).lower() if cycle else None)
    sched_val = schedule.value if isinstance(schedule, TariffSchedule) else (str(schedule).upper() if schedule else None)

    candidates = [
        d for d in definitions
        if d.country_code.upper() == target_country
        and (cycle_val is None or d.cycle == cycle_val or d.cycle.value == cycle_val)
        and (sched_val is None or d.schedule == sched_val or d.schedule.value == sched_val)
    ]

    if not candidates:
        return []

    # Filter definitions valid on reference_date (today)
    active_today_candidates = []
    for c in candidates:
        if c.start_date and c.start_date > ref_d_str:
            continue
        if c.end_date and c.end_date < ref_d_str:
            continue
        active_today_candidates.append(c)

    # Future definitions starting after reference_date (upcoming regulation changeovers)
    future_candidates = [c for c in candidates if c.start_date and c.start_date > ref_d_str]

    results: list[TariffCycleSchedule] = []

    if active_today_candidates:
        has_seasonal = any(c.season is not None for c in active_today_candidates)
        if has_seasonal:
            current_season = get_season_for_date(ref_d_str, country_code=target_country)
            upcoming_season = get_upcoming_season(current_season)

            # 1. Active season today
            cur_season_matches = [c for c in active_today_candidates if c.season == current_season]
            if cur_season_matches:
                cur_season_matches.sort(key=lambda c: c.start_date or "", reverse=True)
                results.append(cur_season_matches[0])

            # 2. Upcoming season from active regulation
            up_season_matches = [c for c in active_today_candidates if c.season == upcoming_season]
            if up_season_matches:
                up_season_matches.sort(key=lambda c: c.start_date or "", reverse=True)
                results.append(up_season_matches[0])
        else:
            # Non-seasonal: pick latest start_date for today
            active_today_candidates.sort(key=lambda c: c.start_date or "", reverse=True)
            results.append(active_today_candidates[0])

    # 3. If future regulation changeovers exist, add the earliest upcoming future regulation period
    if future_candidates:
        future_candidates.sort(key=lambda c: c.start_date or "")
        next_start_date = future_candidates[0].start_date
        next_gen_candidates = [c for c in future_candidates if c.start_date == next_start_date]
        for fg in next_gen_candidates:
            if fg not in results:
                results.append(fg)

    if not results and candidates:
        candidates.sort(key=lambda c: c.start_date or "", reverse=True)
        results.append(candidates[0])

    return results


def find_matching_cycle_schedules(
    definitions: list[TariffCycleSchedule],
    country_code: str | None = "PT",
    cycle: TariffCycle | str | None = None,
    schedule: TariffSchedule | str | None = None,
    effective_date: str | None = None,
    season: str | None = None,
) -> list[TariffCycleSchedule]:
    """Find all applicable TariffCycleSchedule definitions matching country, cycle, schedule, date and season."""
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
        candidates = [d for d in candidates if d.season == season.lower()]

    if not candidates:
        return []

    if effective_date is not None:
        valid_candidates = []
        for c in candidates:
            if c.start_date and c.start_date > effective_date:
                continue
            if c.end_date and c.end_date < effective_date:
                continue
            valid_candidates.append(c)
        candidates = valid_candidates

    if not candidates:
        return []

    # Group candidates by season (None, 'inverno', 'verao', etc.) and pick the latest start_date for each
    by_season: dict[str | None, list[TariffCycleSchedule]] = {}
    for c in candidates:
        season_key = c.season.lower() if c.season else None
        by_season.setdefault(season_key, []).append(c)

    results: list[TariffCycleSchedule] = []
    for s_key, sched_list in by_season.items():
        sched_list.sort(key=lambda c: c.start_date or "", reverse=True)
        results.append(sched_list[0])

    return results


def find_matching_cycle_schedule(
    definitions: list[TariffCycleSchedule],
    country_code: str | None = "PT",
    cycle: TariffCycle | str | None = None,
    schedule: TariffSchedule | str | None = None,
    effective_date: str | None = None,
    season: str | None = None,
) -> TariffCycleSchedule | None:
    """Find the single most applicable TariffCycleSchedule matching country, cycle, schedule, date and season."""
    matches = find_matching_cycle_schedules(
        definitions=definitions,
        country_code=country_code,
        cycle=cycle,
        schedule=schedule,
        effective_date=effective_date,
        season=season,
    )
    if not matches:
        return None

    if season is not None:
        return matches[0]

    # If no season specified, prefer non-seasonal or first available
    non_seasonal = [m for m in matches if m.season is None]
    if non_seasonal:
        return non_seasonal[0]

    return matches[0]


def resolve_all_time_restrictions(
    period: TariffPeriod | str,
    cycle: TariffCycle | str,
    schedule: TariffSchedule | str,
    definitions: list[TariffCycleSchedule] | None = None,
    country_code: str | None = "PT",
    effective_date: str | None = None,
) -> list[list[TimeRestriction]]:
    """Resolve a TOU period across Today's schedule and Upcoming season/regulation schedules into unique lists of TimeRestriction."""
    if definitions is None:
        definitions = load_time_restrictions()

    period_val = period.value if isinstance(period, TariffPeriod) else str(period).lower()
    sched_val = schedule.value if isinstance(schedule, TariffSchedule) else str(schedule).upper()

    # Normalize 2H cheias to fora_vazio
    if sched_val == "2H" and period_val == "cheias":
        period_val = "fora_vazio"

    matched_schedules = find_effective_and_upcoming_schedules(
        definitions=definitions,
        country_code=country_code,
        cycle=cycle,
        schedule=schedule,
        reference_date=effective_date,
    )

    if not matched_schedules:
        return []

    unique_restr_lists: list[list[TimeRestriction]] = []

    for sched in matched_schedules:
        if not sched.periods:
            continue
        for p_enum, restrs in sched.periods.items():
            p_str = p_enum.value if isinstance(p_enum, TariffPeriod) else str(p_enum).lower()
            if p_str == period_val:
                copied = []
                for r in restrs:
                    c = r.model_copy()
                    if c.name is None:
                        c.name = period_val
                    copied.append(c)
                if copied not in unique_restr_lists:
                    unique_restr_lists.append(copied)

    return unique_restr_lists


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
            copied = []
            for r in restrs:
                c = r.model_copy()
                if c.name is None:
                    c.name = period_val
                copied.append(c)
            return copied

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
