"""Legacy CEME comparison CSV exporter.

Exports published BYOE (Bring Your Own Electricity / CEME) plans into a CSV format
matching the historical Portuguese EV community benchmark spreadsheet structure.
"""

from __future__ import annotations

import csv
import datetime
import os
from dataclasses import dataclass
from typing import Any

from tariffs.byoe_generator import find_matching_regulated_fees
from tariffs.model import Plan, Provider
from tariffs.regulated_fees import RegulatedFees, TariffSchedule

# Mapping from (provider_name, base_plan_name) to the exact community contract name
CONTRACT_NAME_MAPPING: dict[tuple[str, str], str] = {
    ("ACP Electric", "CEME Base"): "ACP Electric",
    ("ACP Electric", "CEME Sócio"): "ACP Electric Sócio",
    ("Atlante", "CEME"): "Atlante",
    ("BlueCharge", "CEME"): "BlueCharge",
    ("Charge2Go", "CEME"): "Charge2Go",
    ("Chargemap", "CEME"): "Chargemap",
    ("EDP", "CEME"): "EDP",
    ("EDP", "CEME Bi-horário"): "EDP (Bi-horário)",
    ("EDP", "CEME Casa"): "EDP Casa",
    ("EDP", "CEME Casa Bi-horário"): "EDP Casa (Bi-horário)",
    ("EDP", "CEME Casa + UVE"): "EDP Casa + UVE",
    ("EDP", "CEME Casa + UVE Bi-horário"): "EDP Casa + UVE (Bi-horário)",
    ("EDP", "CEME UVE"): "EDP UVE",
    ("EDP", "CEME UVE Bi-horário"): "EDP UVE (Bi-horário)",
    ("Enable Mobility", "CEME"): "Enable Mobility",
    ("eVaz", "CEME Move Base"): "eVaz Move Base",
    ("eVaz", "CEME Move Volt / Home"): "eVaz Move Volt / Home",
    ("Evio", "CEME"): "Evio",
    ("EVPower", "CEME"): "EVPower",
    ("EZU / AB Energia", "CEME Cartão"): "EZU / AB Energia",
    ("EZU / AB Energia", "CEME App"): "EZU / AB Energia App",
    ("FactorEnergia", "CEME"): "FactorEnergia",
    ("Galp", "CEME Base"): "Galp Electric",
    ("Galp", "CEME App"): "Galp Electric App",
    ("Galp", "CEME Casa"): "Galp Electric Casa",
    ("Goldenergy", "CEME Base"): "Goldenergy",
    ("Goldenergy", "CEME Casa"): "Goldenergy Casa",
    ("Iberdrola", "CEME Base"): "Iberdrola",
    ("Iberdrola", "CEME Casa"): "Iberdrola Casa",
    ("MEO Energia", "CEME M4e/M5e"): "Meo Energia M4e/M5e",
    ("MEO Energia", "CEME M2e/M3e"): "Meo Energia M2e/M3e",
    ("MEO Energia", "CEME Colaboradores"): "Meo Energia Colaboradores",
    ("Miio", "CEME Base"): "Miio",
    ("Miio", "CEME One"): "Miio One",
    ("Mobismart", "CEME Active"): "Mobismart/EVCE Active",
    ("Mobismart", "CEME Pré-Pago"): "Mobismart/EVCE Pré-Pago",
    ("Moeve", "CEME App GOW"): "Moeve App GOW",
    ("Moeve", "CEME App GOW Deco"): "Moeve App GOW Deco",
    ("Moeve", "CEME Cartão"): "Moeve Cartão",
    ("Okeana", "CEME"): "Okeana",
    ("Prio", "CEME (kWh)"): "Prio (kWh)",
    ("Repsol", "CEME"): "Repsol",
    ("Via Verde", "CEME EcoChoice"): "ViaVerde | EcoChoice",
    ("Zunder", "CEME"): "Zunder",
}


def resolve_contract_name(provider_name: str, base_plan_name: str) -> str:
    """Resolve community contract name for a provider and base plan name."""
    key = (provider_name, base_plan_name)
    if key in CONTRACT_NAME_MAPPING:
        return CONTRACT_NAME_MAPPING[key]

    if base_plan_name in ("CEME", "CEME Base"):
        return provider_name

    suffix = base_plan_name.removeprefix("CEME ")
    return f"{provider_name} {suffix}"


def format_eu_number(val: float | None, decimals: int = 4) -> str:
    """Format a floating-point number into European notation using comma decimal."""
    if val is None:
        return ""
    formatted = f"{val:.{decimals}f}"
    return formatted.replace(".", ",")


@dataclass
class GroupedByoeEntry:
    provider: Provider
    base_plan_name: str
    plans: list[Plan]
    cycle: str


def _clean_plan_name(name: str) -> tuple[str, str | None]:
    """Strip cycle suffixes like '(Diário)' or '(Semanal)' and return (base_name, cycle)."""
    if name.endswith(" (Diário)"):
        return name.removesuffix(" (Diário)").strip(), "diario"
    if name.endswith(" (Semanal)"):
        return name.removesuffix(" (Semanal)").strip(), "semanal"
    return name.strip(), None


def _group_byoe_plans(providers: list[Provider]) -> list[GroupedByoeEntry]:
    """Group daily and weekly variants of the same base plan into unified entries."""
    grouped_map: dict[tuple[str, str], list[Plan]] = {}
    provider_map: dict[str, Provider] = {}

    for prov in providers:
        if not prov.publish:
            continue
        provider_map[prov.name] = prov
        for plan in prov.plans:
            if not plan.publish or not plan.is_byoe:
                continue

            base_name, _ = _clean_plan_name(plan.name)
            key = (prov.name, base_name)
            if key not in grouped_map:
                grouped_map[key] = []
            grouped_map[key].append(plan)

    entries: list[GroupedByoeEntry] = []
    for (prov_name, base_name), plan_list in grouped_map.items():
        prov = provider_map[prov_name]
        # Determine cycle representation
        cycles_present = set()
        for p in plan_list:
            _, detected_cycle = _clean_plan_name(p.name)
            cycle_val = detected_cycle or (p.byoe.cycle if p.byoe else None)
            if cycle_val:
                cycles_present.add(cycle_val.lower())

        schedule = plan_list[0].byoe.schedule if plan_list[0].byoe else None
        if schedule == TariffSchedule.SIMPLES or schedule == "1H":
            rep_cycle = "Nenhum"
        elif "diario" in cycles_present and "semanal" in cycles_present:
            rep_cycle = "Ambos"
        elif "semanal" in cycles_present:
            rep_cycle = "Semanal"
        elif "diario" in cycles_present:
            rep_cycle = "Diário"
        else:
            rep_cycle = "Diário"

        entries.append(
            GroupedByoeEntry(
                provider=prov,
                base_plan_name=base_name,
                plans=plan_list,
                cycle=rep_cycle,
            )
        )

    return entries


def export_byoe_to_csv(
    providers: list[Provider],
    regulated_fees: list[RegulatedFees] | None,
    output_path: str,
    reference_date: str | None = None,
) -> str:
    """Export published BYOE plans into a CSV following CEME Comparação Preços structure."""
    ref_date = reference_date or datetime.datetime.now(datetime.UTC).date().isoformat()
    matched_rf = (
        find_matching_regulated_fees(regulated_fees, country_code="PT", effective_date=ref_date)
        if regulated_fees
        else None
    )

    # Regulated fee components for PT
    iec_rate = matched_rf.iec if matched_rf and matched_rf.iec is not None else 0.0010
    egme_fee = (
        matched_rf.egme_connection
        if matched_rf and matched_rf.egme_connection is not None
        else 0.1088
    )
    vat_rate = matched_rf.vat if matched_rf and matched_rf.vat is not None else 0.23

    # TAR rates for BT and MT (2H / 3H)
    tar_bt_cheias = 0.1192
    tar_bt_vazio = 0.0266
    tar_bt_ponta = 0.2807
    tar_mt_cheias = 0.0812
    tar_mt_vazio = 0.0157
    tar_mt_ponta = 0.2410

    if matched_rf and matched_rf.tar_variants:
        for tv in matched_rf.tar_variants:
            v_level = (
                tv.voltage_level.value
                if hasattr(tv.voltage_level, "value")
                else str(tv.voltage_level)
            )
            sched = tv.schedule.value if hasattr(tv.schedule, "value") else str(tv.schedule)
            rates_dict = {
                (r.period.value if hasattr(r.period, "value") else str(r.period)): r.rate
                for r in tv.rates
            }
            if v_level == "BT":
                if sched == "2H":
                    tar_bt_cheias = rates_dict.get("cheias", tar_bt_cheias)
                    tar_bt_vazio = rates_dict.get("vazio", tar_bt_vazio)
                elif sched == "3H":
                    tar_bt_ponta = rates_dict.get("ponta", tar_bt_ponta)
            elif v_level == "MT":
                if sched == "2H":
                    tar_mt_cheias = rates_dict.get("cheias", tar_mt_cheias)
                    tar_mt_vazio = rates_dict.get("vazio", tar_mt_vazio)
                elif sched == "3H":
                    tar_mt_ponta = rates_dict.get("ponta", tar_mt_ponta)

    header = [
        "CEME | CONTRATO",
        "Condicionantes",
        "URL",
        "Data atualização",
        "Data Tarifário",
        "Data Fim Tarifário",
        "Producao Renovavel",
        "Tarifa",
        "Ciclo",
        "Inclui EGME",
        "Inclui IEC",
        "Inclui TAR",
        "Ativacao",
        "Comissao OPC %",
        "Ponta (cTAR)",
        "Cheias / Fora de Vazio (cTAR)",
        "Vazio (cTAR)",
        "Ponta (sTAR)",
        "Cheias / Fora de Vazio (sTAR)",
        "Vazio (sTAR)",
        "Funcionalidades",
        "Mensalidade",
        "Inclui OPC",
        "Inclui IVA",
        "Tarifa OCPI",
        "IEC",
        "Ponta (BT)",
        "Cheias / Fora de Vazio (BT)",
        "Vazio (BT)",
        "Ponta (MT)",
        "Cheias / Fora de Vazio (MT)",
        "Vazio (MT)",
        "Sorting Column",
        "Ranking",
    ]

    grouped_entries = _group_byoe_plans(providers)
    data_rows: list[dict[str, Any]] = []

    for entry in grouped_entries:
        prov = entry.provider
        primary_plan = entry.plans[0]
        byoe = primary_plan.byoe
        if not byoe:
            continue

        contract_name = resolve_contract_name(prov.name, entry.base_plan_name)

        # Conditions / notes in Portuguese
        cond_text = ""
        if primary_plan.notes:
            pt_notes = [n.text for n in primary_plan.notes if n.language == "pt"]
            cond_text = pt_notes[0] if pt_notes else primary_plan.notes[0].text

        url = (
            prov.source.urls[0]
            if prov.source and prov.source.urls
            else prov.url or ""
        )
        updated_at = (
            prov.source.last_updated
            if prov.source and prov.source.last_updated
            else prov.updated_at or ""
        )
        start_date = byoe.start_date or primary_plan.start_date or ""
        end_date = primary_plan.end_date or ""
        renewable = (
            "TRUE"
            if byoe.renewable_energy
            else ("FALSE" if byoe.renewable_energy is not None else "")
        )

        sched_str = (
            byoe.schedule.value
            if hasattr(byoe.schedule, "value")
            else str(byoe.schedule or "2H")
        )
        cycle_str = entry.cycle

        inc_egme = bool(byoe.includes_egme)
        inc_iec = bool(byoe.includes_iec)
        inc_tar = bool(byoe.includes_tar)

        ativ_fee = byoe.activation_fee if byoe.activation_fee is not None else 0.0
        ativ_str = format_eu_number(ativ_fee, decimals=4)
        opc_pct_str = (
            format_eu_number(byoe.opc_commission_pct, decimals=5)
            if byoe.opc_commission_pct is not None
            else ""
        )

        # Determine energy rates (handling both top-level and rates_by_voltage)
        ponta_rate: float | None = None
        cheias_rate: float | None = None
        vazio_rate: float | None = None
        mt_ponta_rate: float | None = None
        mt_cheias_rate: float | None = None
        mt_vazio_rate: float | None = None

        if byoe.rates_by_voltage:
            bt_rates = byoe.rates_by_voltage.get("BT")
            mt_rates = byoe.rates_by_voltage.get("MT")
            if bt_rates:
                if sched_str == "1H":
                    cheias_rate = bt_rates.all_day
                    vazio_rate = bt_rates.all_day
                else:
                    cheias_rate = (
                        bt_rates.fora_vazio
                        if bt_rates.fora_vazio is not None
                        else bt_rates.cheias
                    )
                    vazio_rate = bt_rates.vazio
                    ponta_rate = bt_rates.ponta
            if mt_rates:
                if sched_str == "1H":
                    mt_cheias_rate = mt_rates.all_day
                    mt_vazio_rate = mt_rates.all_day
                else:
                    mt_cheias_rate = (
                        mt_rates.fora_vazio
                        if mt_rates.fora_vazio is not None
                        else mt_rates.cheias
                    )
                    mt_vazio_rate = mt_rates.vazio
                    mt_ponta_rate = mt_rates.ponta
        elif sched_str == "1H":
            cheias_rate = byoe.all_day
            vazio_rate = byoe.all_day
        else:
            cheias_rate = byoe.fora_vazio if byoe.fora_vazio is not None else byoe.cheias
            vazio_rate = byoe.vazio
            ponta_rate = byoe.ponta

        # Default MT to BT rates if not specified separately
        if mt_cheias_rate is None:
            mt_cheias_rate = cheias_rate
        if mt_vazio_rate is None:
            mt_vazio_rate = vazio_rate
        if mt_ponta_rate is None:
            mt_ponta_rate = ponta_rate

        # Populate cTAR / sTAR fields (reflecting base/BT energy rate)
        if inc_tar:
            ponta_ctar_str = format_eu_number(ponta_rate, 4) if ponta_rate is not None else ""
            cheias_ctar_str = format_eu_number(cheias_rate, 4) if cheias_rate is not None else ""
            vazio_ctar_str = format_eu_number(vazio_rate, 4) if vazio_rate is not None else ""
            ponta_star_str = ""
            cheias_star_str = ""
            vazio_star_str = ""
        else:
            ponta_ctar_str = ""
            cheias_ctar_str = ""
            vazio_ctar_str = ""
            ponta_star_str = format_eu_number(ponta_rate, 4) if ponta_rate is not None else ""
            cheias_star_str = format_eu_number(cheias_rate, 4) if cheias_rate is not None else ""
            vazio_star_str = format_eu_number(vazio_rate, 4) if vazio_rate is not None else ""

        # Payment methods
        pm_strs = [
            pm.value if hasattr(pm, "value") else str(pm)
            for pm in (primary_plan.payment_methods or [])
        ]
        has_card = any("CARD" in m for m in pm_strs)
        has_app = any("APP" in m for m in pm_strs)
        if has_card and has_app:
            func_str = "CARD, APP"
        elif has_card:
            func_str = "CARD"
        elif has_app:
            func_str = "APP"
        else:
            func_str = ""

        cost_str = format_eu_number(primary_plan.cost, 2) if primary_plan.cost is not None else ""
        inc_opc_str = "FALSE"
        inc_vat_str = "TRUE" if byoe.includes_vat else ""
        ocpi_str = ""
        iec_col_str = format_eu_number(iec_rate, 4)

        # Estimated TOU calculations (BT & MT)
        iec_addon = 0.0 if inc_iec else iec_rate

        if inc_tar:
            bt_cheias = (cheias_rate + iec_addon) if cheias_rate is not None else None
            bt_vazio = (vazio_rate + iec_addon) if vazio_rate is not None else None
            bt_ponta = (ponta_rate + iec_addon) if ponta_rate is not None else None
            mt_cheias = (mt_cheias_rate + iec_addon) if mt_cheias_rate is not None else None
            mt_vazio = (mt_vazio_rate + iec_addon) if mt_vazio_rate is not None else None
            mt_ponta = (mt_ponta_rate + iec_addon) if mt_ponta_rate is not None else None
        else:
            bt_cheias = (cheias_rate + tar_bt_cheias + iec_addon) if cheias_rate is not None else None
            bt_vazio = (vazio_rate + tar_bt_vazio + iec_addon) if vazio_rate is not None else None
            bt_ponta = (ponta_rate + tar_bt_ponta + iec_addon) if ponta_rate is not None else None
            mt_cheias = (mt_cheias_rate + tar_mt_cheias + iec_addon) if mt_cheias_rate is not None else None
            mt_vazio = (mt_vazio_rate + tar_mt_vazio + iec_addon) if mt_vazio_rate is not None else None
            mt_ponta = (mt_ponta_rate + tar_mt_ponta + iec_addon) if mt_ponta_rate is not None else None

        bt_ponta_str = format_eu_number(bt_ponta, 3) if bt_ponta is not None else ""
        bt_cheias_str = format_eu_number(bt_cheias, 3) if bt_cheias is not None else ""
        bt_vazio_str = format_eu_number(bt_vazio, 3) if bt_vazio is not None else ""
        mt_ponta_str = format_eu_number(mt_ponta, 3) if mt_ponta is not None else ""
        mt_cheias_str = format_eu_number(mt_cheias, 3) if mt_cheias is not None else ""
        mt_vazio_str = format_eu_number(mt_vazio, 3) if mt_vazio is not None else ""

        # Simulation cost (Sorting Column)
        # Session assumption: 35 kWh charging session (86% Cheias / 14% Vazio)
        kwh_session = 35.0
        c_rate = cheias_rate or 0.0
        v_rate = vazio_rate or 0.0

        if inc_tar:
            cost_kwh = (0.86 * c_rate + 0.14 * v_rate) * (1.0 + vat_rate)
            if not inc_iec:
                cost_kwh += iec_rate * (1.0 + vat_rate)
        else:
            w_energy = 0.86 * c_rate + 0.14 * v_rate
            w_tar = 0.86 * tar_bt_cheias + 0.14 * tar_bt_vazio
            cost_kwh = w_energy * (1.0 + vat_rate) + w_tar
            if not inc_iec:
                cost_kwh += iec_rate
            if not inc_egme:
                cost_kwh += egme_fee / kwh_session

        if ativ_fee > 0:
            cost_kwh += ativ_fee / kwh_session

        sorting_val = round(cost_kwh, 3)
        sort_col_str = format_eu_number(sorting_val, 3)

        data_rows.append({
            "contract_name": contract_name,
            "cond_text": cond_text,
            "url": url,
            "updated_at": updated_at,
            "start_date": start_date,
            "end_date": end_date,
            "renewable": renewable,
            "sched_str": sched_str,
            "cycle_str": cycle_str,
            "inc_egme": "TRUE" if inc_egme else "FALSE",
            "inc_iec": "TRUE" if inc_iec else "FALSE",
            "inc_tar": "TRUE" if inc_tar else "FALSE",
            "ativ_str": ativ_str,
            "opc_pct_str": opc_pct_str,
            "ponta_ctar_str": ponta_ctar_str,
            "cheias_ctar_str": cheias_ctar_str,
            "vazio_ctar_str": vazio_ctar_str,
            "ponta_star_str": ponta_star_str,
            "cheias_star_str": cheias_star_str,
            "vazio_star_str": vazio_star_str,
            "func_str": func_str,
            "cost_str": cost_str,
            "inc_opc_str": inc_opc_str,
            "inc_vat_str": inc_vat_str,
            "ocpi_str": ocpi_str,
            "iec_col_str": iec_col_str,
            "bt_ponta_str": bt_ponta_str,
            "bt_cheias_str": bt_cheias_str,
            "bt_vazio_str": bt_vazio_str,
            "mt_ponta_str": mt_ponta_str,
            "mt_cheias_str": mt_cheias_str,
            "mt_vazio_str": mt_vazio_str,
            "sorting_val": sorting_val,
            "sort_col_str": sort_col_str,
        })

    # Sort data rows by sorting_val ascending, secondary by contract name
    data_rows.sort(key=lambda r: (r["sorting_val"], r["contract_name"]))

    # Output directory
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(header)

        for rank_idx, r in enumerate(data_rows, start=1):
            row = [
                r["contract_name"],
                r["cond_text"],
                r["url"],
                r["updated_at"],
                r["start_date"],
                r["end_date"],
                r["renewable"],
                r["sched_str"],
                r["cycle_str"],
                r["inc_egme"],
                r["inc_iec"],
                r["inc_tar"],
                r["ativ_str"],
                r["opc_pct_str"],
                r["ponta_ctar_str"],
                r["cheias_ctar_str"],
                r["vazio_ctar_str"],
                r["ponta_star_str"],
                r["cheias_star_str"],
                r["vazio_star_str"],
                r["func_str"],
                r["cost_str"],
                r["inc_opc_str"],
                r["inc_vat_str"],
                r["ocpi_str"],
                r["iec_col_str"],
                r["bt_ponta_str"],
                r["bt_cheias_str"],
                r["bt_vazio_str"],
                r["mt_ponta_str"],
                r["mt_cheias_str"],
                r["mt_vazio_str"],
                r["sort_col_str"],
                str(rank_idx),
            ]
            writer.writerow(row)

    return output_path
