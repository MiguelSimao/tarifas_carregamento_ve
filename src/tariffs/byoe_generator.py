"""BYOE (Bring Your Own Electricity / CEME) tariff generator."""

import datetime

from .model import (
    ByoeConfig,
    DimensionType,
    MobieFeeType,
    MobieVoltageLevel,
    Network,
    Plan,
    Tariff,
)
from .regulated_fees import (
    RegulatedFees,
    TariffCycle,
    TariffCycleSchedule,
    TariffPeriod,
    TariffSchedule,
)
from .time_restrictions import resolve_all_time_restrictions


def find_matching_regulated_fees(
    regulated_fees_list: list[RegulatedFees],
    country_code: str | None = "PT",
    effective_date: str | None = None,
) -> RegulatedFees | None:
    """Find the most applicable RegulatedFees matching country code and date."""
    target_country = (country_code or "PT").upper()
    matching_country = [rf for rf in regulated_fees_list if rf.country_code.upper() == target_country]
    if not matching_country:
        return None

    if effective_date is not None:
        valid_fees = [rf for rf in matching_country if rf.effective_date <= effective_date]
        if valid_fees:
            valid_fees.sort(key=lambda rf: rf.effective_date, reverse=True)
            return valid_fees[0]

    # Fallback to the latest effective_date for that country
    matching_country.sort(key=lambda rf: rf.effective_date, reverse=True)
    return matching_country[0]


def _generate_tariffs_for_restriction(
    byoe: ByoeConfig,
    reg_fees: RegulatedFees,
    time_restrictions_list: list[TariffCycleSchedule] | None = None,
    reference_date: str | None = None,
    country_code: str | None = "PT",
    power_type: str | None = None,
    min_power: float | None = None,
    max_power: float | None = None,
    voltage_level: MobieVoltageLevel | None = None,
) -> list[Tariff]:
    cycle = byoe.cycle or TariffCycle.DIARIO
    schedule = byoe.schedule
    today_ref_date = reference_date or datetime.date.today().isoformat()

    generated_tariffs: list[Tariff] = []

    # 1. Flat activation fee (if specified)
    if byoe.activation_fee is not None and round(byoe.activation_fee, 4) > 0:
        generated_tariffs.append(
            Tariff(
                type=power_type,
                min=min_power,
                max=max_power,
                price=round(byoe.activation_fee, 4),
                unit=DimensionType.FLAT,
            )
        )

    # 2. EGME connection fee (flat) from regulated fees (if not included in BYOE plan)
    if not byoe.includes_egme and round(reg_fees.egme_connection, 4) > 0:
        generated_tariffs.append(
            Tariff(
                type=power_type,
                min=min_power,
                max=max_power,
                price=round(reg_fees.egme_connection, 4),
                unit=DimensionType.FLAT,
                mobie_fee_type=MobieFeeType.EGME,
            )
        )

    # 3. IEC regulated energy tax from regulated fees (if not included in BYOE plan)
    if not byoe.includes_iec and round(reg_fees.iec, 4) > 0:
        generated_tariffs.append(
            Tariff(
                type=power_type,
                min=min_power,
                max=max_power,
                price=round(reg_fees.iec, 4),
                unit=DimensionType.ENERGY,
                mobie_fee_type=MobieFeeType.IEC,
            )
        )

    # 4. CEME energy rates
    if schedule == TariffSchedule.SIMPLES:
        single_rate = byoe.all_day
        if single_rate is None:
            single_rate = (
                byoe.fora_vazio
                if byoe.fora_vazio is not None
                else (byoe.cheias if byoe.cheias is not None else byoe.vazio)
            )
        if single_rate is not None:
            generated_tariffs.append(
                Tariff(
                    type=power_type,
                    min=min_power,
                    max=max_power,
                    mobie_voltage_level=voltage_level,
                    price=round(single_rate, 4),
                    unit=DimensionType.ENERGY,
                    mobie_fee_type=MobieFeeType.CEME,
                )
            )
    else:
        rates_map: dict[TariffPeriod, float] = {}

        if schedule == TariffSchedule.BIHORARIO:
            if byoe.vazio is not None:
                rates_map[TariffPeriod.VAZIO] = byoe.vazio
            fora_vazio_rate = (
                byoe.fora_vazio
                if byoe.fora_vazio is not None
                else byoe.cheias
            )
            if fora_vazio_rate is not None:
                rates_map[TariffPeriod.FORA_VAZIO] = fora_vazio_rate
        elif schedule == TariffSchedule.TRIHORARIO:
            if byoe.vazio is not None:
                rates_map[TariffPeriod.VAZIO] = byoe.vazio
            if byoe.cheias is not None:
                rates_map[TariffPeriod.CHEIAS] = byoe.cheias
            if byoe.ponta is not None:
                rates_map[TariffPeriod.PONTA] = byoe.ponta
        else:
            # Fallback / Single rate
            if byoe.vazio is not None:
                rates_map[TariffPeriod.VAZIO] = byoe.vazio
            if byoe.fora_vazio is not None:
                rates_map[TariffPeriod.FORA_VAZIO] = byoe.fora_vazio
            elif byoe.cheias is not None:
                rates_map[TariffPeriod.CHEIAS] = byoe.cheias

        if rates_map:
            unique_rates = set(rates_map.values())
            if len(unique_rates) == 1:
                rate = next(iter(unique_rates))
                generated_tariffs.append(
                    Tariff(
                        type=power_type,
                        min=min_power,
                        max=max_power,
                        mobie_voltage_level=voltage_level,
                        price=round(rate, 4),
                        unit=DimensionType.ENERGY,
                        mobie_fee_type=MobieFeeType.CEME,
                    )
                )
            else:
                for period, rate in rates_map.items():
                    restrs_list = resolve_all_time_restrictions(
                        period=period,
                        cycle=cycle,
                        schedule=schedule or TariffSchedule.BIHORARIO,
                        definitions=time_restrictions_list,
                        country_code=country_code,
                        effective_date=today_ref_date,
                    )
                    if restrs_list:
                        for restrs in restrs_list:
                            generated_tariffs.append(
                                Tariff(
                                    type=power_type,
                                    min=min_power,
                                    max=max_power,
                                    mobie_voltage_level=voltage_level,
                                    price=round(rate, 4),
                                    unit=DimensionType.ENERGY,
                                    mobie_fee_type=MobieFeeType.CEME,
                                    time_restrictions=restrs,
                                )
                            )
                    else:
                        generated_tariffs.append(
                            Tariff(
                                type=power_type,
                                min=min_power,
                                max=max_power,
                                mobie_voltage_level=voltage_level,
                                price=round(rate, 4),
                                unit=DimensionType.ENERGY,
                                mobie_fee_type=MobieFeeType.CEME,
                            )
                        )

    # 5. TAR regulated energy fees (if not included in BYOE plan)
    if not byoe.includes_tar:
        for variant in reg_fees.tar_variants:
            if schedule is not None and variant.schedule is not None and variant.schedule != schedule:
                continue
            if byoe.cycle is not None and variant.cycle is not None and variant.cycle != byoe.cycle:
                continue

            v_level = MobieVoltageLevel(variant.voltage_level)

            # Filter by voltage_level if specified
            if voltage_level is not None and v_level != voltage_level:
                continue

            for rate_item in variant.rates:
                period = rate_item.period
                if schedule == TariffSchedule.BIHORARIO and period == TariffPeriod.CHEIAS:
                    period = TariffPeriod.FORA_VAZIO

                restrs_list = resolve_all_time_restrictions(
                    period=period,
                    cycle=cycle,
                    schedule=schedule or variant.schedule or TariffSchedule.BIHORARIO,
                    definitions=time_restrictions_list,
                    country_code=country_code,
                    effective_date=today_ref_date,
                )

                if restrs_list:
                    for restrs in restrs_list:
                        generated_tariffs.append(
                            Tariff(
                                type=power_type,
                                min=min_power,
                                max=max_power,
                                price=round(rate_item.rate, 4),
                                unit=DimensionType.ENERGY,
                                mobie_fee_type=MobieFeeType.TAR,
                                mobie_voltage_level=v_level,
                                time_restrictions=restrs,
                            )
                        )
                else:
                    generated_tariffs.append(
                        Tariff(
                            type=power_type,
                            min=min_power,
                            max=max_power,
                            price=round(rate_item.rate, 4),
                            unit=DimensionType.ENERGY,
                            mobie_fee_type=MobieFeeType.TAR,
                            mobie_voltage_level=v_level,
                        )
                    )

    return generated_tariffs


def _expand_single_byoe_plan(
    plan: Plan,
    regulated_fees_list: list[RegulatedFees],
    time_restrictions_list: list[TariffCycleSchedule] | None = None,
    reference_date: str | None = None,
    country_code: str | None = None,
) -> Plan:
    """Expand tariffs for a single BYOE plan for a specific country/region."""
    if not plan.is_byoe or not plan.byoe:
        return plan

    target_country = country_code or plan.country_code or "PT"
    today_ref_date = reference_date or datetime.date.today().isoformat()

    # Check if BYOE rates are provided or tariffs need generating
    has_byoe_rates = (
        plan.byoe.all_day is not None
        or plan.byoe.vazio is not None
        or plan.byoe.cheias is not None
        or plan.byoe.fora_vazio is not None
        or plan.byoe.ponta is not None
        or plan.byoe.activation_fee is not None
    )

    has_placeholders = any(
        t.is_byoe_placeholder
        for n in plan.networks
        for t in n.tariffs
    )

    # If no rates provided, no placeholders, and network already has concrete tariffs, don't overwrite
    has_existing_tariffs = any(len(n.tariffs) > 0 for n in plan.networks)
    if not has_byoe_rates and not has_placeholders and has_existing_tariffs:
        return plan

    reg_fees = find_matching_regulated_fees(
        regulated_fees_list,
        country_code=target_country,
        effective_date=today_ref_date,
    )
    if not reg_fees:
        raise ValueError(
            f"No regulated fees found for country '{target_country}' "
            f"and date '{today_ref_date}' for BYOE plan '{plan.name}'"
        )

    # Associate regional VAT and includes_vat if not explicitly provided on the plan
    if plan.vat is None and reg_fees.vat is not None:
        plan.vat = reg_fees.vat
    if plan.includes_vat is None and plan.byoe and plan.byoe.includes_vat is not None:
        plan.includes_vat = plan.byoe.includes_vat

    if not plan.networks:
        plan.networks = [Network(network_id="MOBIE")]

    for network in plan.networks:
        placeholders = [t for t in network.tariffs if t.is_byoe_placeholder]
        if placeholders:
            expanded_tariffs: list[Tariff] = []
            for placeholder in placeholders:
                expanded_tariffs.extend(
                    _generate_tariffs_for_restriction(
                        byoe=plan.byoe,
                        reg_fees=reg_fees,
                        time_restrictions_list=time_restrictions_list,
                        reference_date=today_ref_date,
                        country_code=target_country,
                        power_type=placeholder.type,
                        min_power=placeholder.min,
                        max_power=placeholder.max,
                        voltage_level=placeholder.mobie_voltage_level,
                    )
                )
            network.tariffs = expanded_tariffs
        else:
            if has_byoe_rates or not network.tariffs:
                network.tariffs = _generate_tariffs_for_restriction(
                    byoe=plan.byoe,
                    reg_fees=reg_fees,
                    time_restrictions_list=time_restrictions_list,
                    reference_date=today_ref_date,
                    country_code=target_country,
                    power_type=None,
                    min_power=None,
                    max_power=None,
                    voltage_level=None,
                )

    return plan


def expand_byoe_plans(
    plan: Plan,
    regulated_fees_list: list[RegulatedFees],
    time_restrictions_list: list[TariffCycleSchedule] | None = None,
    reference_date: str | None = None,
) -> list[Plan]:
    """Expand a BYOE plan into one or more regional plans (if regions are specified)
    by calculating network tariffs from BYOE rates, regional regulated fees, and regional time restrictions.
    """
    if not plan.is_byoe or not plan.byoe:
        return [plan]

    target_regions = plan.regions or [plan.country_code or "PT"]
    expanded_plans: list[Plan] = []

    for region in target_regions:
        regional_plan = plan.model_copy(deep=True)
        regional_plan.country_code = region
        regional_plan.regions = None
        _expand_single_byoe_plan(
            plan=regional_plan,
            regulated_fees_list=regulated_fees_list,
            time_restrictions_list=time_restrictions_list,
            reference_date=reference_date,
            country_code=region,
        )
        expanded_plans.append(regional_plan)

    return expanded_plans


def expand_byoe_plan(
    plan: Plan,
    regulated_fees_list: list[RegulatedFees],
    time_restrictions_list: list[TariffCycleSchedule] | None = None,
    reference_date: str | None = None,
) -> Plan:
    """Expand a single BYOE plan (or first region if multiple regions specified)."""
    return expand_byoe_plans(
        plan=plan,
        regulated_fees_list=regulated_fees_list,
        time_restrictions_list=time_restrictions_list,
        reference_date=reference_date,
    )[0]


