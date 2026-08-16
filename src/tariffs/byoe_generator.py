"""BYOE (Bring Your Own Electricity / CEME) tariff generator."""

from .model import (
    DimensionType,
    MobieFeeType,
    MobieVoltageLevel,
    Network,
    Plan,
    Tariff,
)
from .regulated_fees import RegulatedFees, TariffPeriod, TariffSchedule


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


def expand_byoe_plan(
    plan: Plan,
    regulated_fees_list: list[RegulatedFees],
) -> Plan:
    """Expand a BYOE plan by calculating network tariffs from BYOE rates and regulated fees."""
    if not plan.is_byoe or not plan.byoe:
        return plan

    # Check if BYOE rates are provided or tariffs need generating
    has_byoe_rates = (
        plan.byoe.vazio is not None
        or plan.byoe.cheias is not None
        or plan.byoe.fora_vazio is not None
        or plan.byoe.ponta is not None
        or plan.byoe.activation_fee is not None
    )

    # If no rates provided and network already has tariffs, don't overwrite
    has_existing_tariffs = any(len(n.tariffs) > 0 for n in plan.networks)
    if not has_byoe_rates and has_existing_tariffs:
        return plan

    effective_date = plan.byoe.start_date or plan.start_date
    reg_fees = find_matching_regulated_fees(
        regulated_fees_list,
        country_code=plan.country_code,
        effective_date=effective_date,
    )
    if not reg_fees:
        raise ValueError(
            f"No regulated fees found for country '{plan.country_code or 'PT'}' "
            f"and date '{effective_date}' for BYOE plan '{plan.name}'"
        )

    generated_tariffs: list[Tariff] = []

    # 1. Flat activation fee (if specified)
    if plan.byoe.activation_fee is not None and round(plan.byoe.activation_fee, 4) > 0:
        generated_tariffs.append(
            Tariff(
                price=round(plan.byoe.activation_fee, 4),
                unit=DimensionType.FLAT,
            )
        )

    # 2. EGME connection fee (flat) from regulated fees (if not included in BYOE plan)
    if not plan.byoe.includes_egme and round(reg_fees.egme_connection, 4) > 0:
        generated_tariffs.append(
            Tariff(
                price=round(reg_fees.egme_connection, 4),
                unit=DimensionType.FLAT,
                mobie_fee_type=MobieFeeType.EGME,
            )
        )

    # 2. TOU energy rates
    schedule = plan.byoe.schedule
    rates_map: dict[TariffPeriod, float] = {}

    if schedule == TariffSchedule.BIHORARIO:
        if plan.byoe.vazio is not None:
            rates_map[TariffPeriod.VAZIO] = plan.byoe.vazio
        fora_vazio_rate = (
            plan.byoe.fora_vazio
            if plan.byoe.fora_vazio is not None
            else plan.byoe.cheias
        )
        if fora_vazio_rate is not None:
            rates_map[TariffPeriod.FORA_VAZIO] = fora_vazio_rate
    elif schedule == TariffSchedule.TRIHORARIO:
        if plan.byoe.vazio is not None:
            rates_map[TariffPeriod.VAZIO] = plan.byoe.vazio
        if plan.byoe.cheias is not None:
            rates_map[TariffPeriod.CHEIAS] = plan.byoe.cheias
        if plan.byoe.ponta is not None:
            rates_map[TariffPeriod.PONTA] = plan.byoe.ponta
    else:
        # Fallback / Single rate
        if plan.byoe.vazio is not None:
            rates_map[TariffPeriod.VAZIO] = plan.byoe.vazio
        if plan.byoe.fora_vazio is not None:
            rates_map[TariffPeriod.FORA_VAZIO] = plan.byoe.fora_vazio
        elif plan.byoe.cheias is not None:
            rates_map[TariffPeriod.CHEIAS] = plan.byoe.cheias

    iec_add = 0.0 if plan.byoe.includes_iec else reg_fees.iec

    for variant in reg_fees.tar_variants:
        if schedule is not None and variant.schedule is not None and variant.schedule != schedule:
            continue
        if plan.byoe.cycle is not None and variant.cycle is not None and variant.cycle != plan.byoe.cycle:
            continue

        voltage_level = MobieVoltageLevel(variant.voltage_level)

        for rate_item in variant.rates:
            period = rate_item.period
            if schedule == TariffSchedule.BIHORARIO and period == TariffPeriod.CHEIAS:
                period = TariffPeriod.FORA_VAZIO

            base_rate = rates_map.get(period)
            if base_rate is None:
                continue

            tar_add = 0.0 if plan.byoe.includes_tar else rate_item.rate
            total_price = round(base_rate + tar_add + iec_add, 4)

            generated_tariffs.append(
                Tariff(
                    type=plan.byoe.power_type,
                    price=total_price,
                    unit=DimensionType.ENERGY,
                    mobie_voltage_level=voltage_level,
                    tou_period=period,
                )
            )

    # 3. Attach generated tariffs to network
    if plan.networks:
        # Find MOBIE network or use first
        mobie_net = next((n for n in plan.networks if n.network_id == "MOBIE"), plan.networks[0])
        mobie_net.tariffs = generated_tariffs
    else:
        plan.networks = [Network(network_id="MOBIE", tariffs=generated_tariffs)]

    return plan
