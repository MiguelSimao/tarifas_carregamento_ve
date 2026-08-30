"""Import CEME plans from 'CEME Comparação Preços - Fonte.csv' into 'data/pt/byoe_emsps/'."""

import csv
import re
from pathlib import Path

import yaml

CSV_PATH = "CEME Comparação Preços - Fonte.csv"
BYOE_DIR = Path("data/pt/byoe_emsps")


def parse_float(val: str | None) -> float | None:
    if not val:
        return None
    val = val.strip().replace(",", ".")
    return float(val) if val else None


def parse_bool(val: str | None) -> bool | None:
    if not val:
        return None
    v = val.strip().upper()
    if v == "TRUE":
        return True
    if v == "FALSE":
        return False
    return None


# Map CSV row contract name to provider config
PROVIDER_MAPPING = {
    "ACP Electric": {"provider": "ACP Electric", "file": "acp_electric.yaml"},
    "ACP Electric Sócio": {"provider": "ACP Electric", "file": "acp_electric.yaml"},
    "Atlante": {"provider": "Atlante", "file": "atlante.yaml"},
    "BlueCharge": {"provider": "BlueCharge", "file": "bluecharge.yaml"},
    "Charge2Go": {"provider": "Charge2Go", "file": "charge2go.yaml"},
    "Chargemap": {"provider": "Chargemap", "file": "chargemap.yaml"},
    "EDP": {"provider": "EDP", "file": "edp.yaml"},
    "EDP (Bi-horário)": {"provider": "EDP", "file": "edp.yaml"},
    "EDP Casa": {"provider": "EDP", "file": "edp.yaml"},
    "EDP Casa (Bi-horário)": {"provider": "EDP", "file": "edp.yaml"},
    "EDP Casa + UVE": {"provider": "EDP", "file": "edp.yaml"},
    "EDP Casa + UVE (Bi-horário)": {"provider": "EDP", "file": "edp.yaml"},
    "EDP UVE": {"provider": "EDP", "file": "edp.yaml"},
    "EDP UVE (Bi-horário)": {"provider": "EDP", "file": "edp.yaml"},
    "Enable Mobility": {"provider": "Enable Mobility", "file": "enable_mobility.yaml"},
    "eVaz Move Base": {"provider": "eVaz", "file": "evaz.yaml"},
    "eVaz Move Volt / Home": {"provider": "eVaz", "file": "evaz.yaml"},
    "Evio": {"provider": "Evio", "file": "evio.yaml"},
    "EVPower": {"provider": "EVPower", "file": "evpower.yaml"},
    "EZU / AB Energia": {"provider": "EZU / AB Energia", "file": "ezu.yaml"},
    "EZU / AB Energia App": {"provider": "EZU / AB Energia", "file": "ezu.yaml"},
    "FactorEnergia": {"provider": "FactorEnergia", "file": "factorenergia.yaml"},
    "Galp Electric": {"provider": "Galp", "file": "galp.yaml"},
    "Galp Electric App + OPC": {"provider": "Galp", "file": "galp.yaml"},
    "Galp Electric Casa + OPC": {"provider": "Galp", "file": "galp.yaml"},
    "Galp Electric App": {"provider": "Galp", "file": "galp.yaml"},
    "Galp Electric Casa": {"provider": "Galp", "file": "galp.yaml"},
    "Goldenergy": {"provider": "Goldenergy", "file": "goldenergy.yaml"},
    "Goldenergy Casa": {"provider": "Goldenergy", "file": "goldenergy.yaml"},
    "Iberdrola": {"provider": "Iberdrola", "file": "iberdrola.yaml"},
    "Iberdrola Casa": {"provider": "Iberdrola", "file": "iberdrola.yaml"},
    "Meo Energia M4e/M5e": {"provider": "MEO Energia", "file": "meo_energia.yaml"},
    "Meo Energia M2e/M3e": {"provider": "MEO Energia", "file": "meo_energia.yaml"},
    "Meo Energia Colaboradores": {
        "provider": "MEO Energia",
        "file": "meo_energia.yaml",
    },
    "Miio": {"provider": "Miio", "file": "miio.yaml"},
    "Miio One": {"provider": "Miio", "file": "miio.yaml"},
    "Mobismart/EVCE Active": {"provider": "Mobismart", "file": "mobismart.yaml"},
    "Mobismart/EVCE Pré-Pago": {"provider": "Mobismart", "file": "mobismart.yaml"},
    "Moeve App GOW": {"provider": "Moeve", "file": "moeve.yaml"},
    "Moeve App GOW Deco": {"provider": "Moeve", "file": "moeve.yaml"},
    "Moeve Cartão": {"provider": "Moeve", "file": "moeve.yaml"},
    "Okeana": {"provider": "Okeana", "file": "okeana.yaml"},
    "Prio (kWh)": {"provider": "Prio", "file": "prio.yaml"},
    "Repsol": {"provider": "Repsol", "file": "repsol.yaml"},
    "ViaVerde | EcoChoice": {"provider": "Via Verde", "file": "via_verde.yaml"},
    "Zunder": {"provider": "Zunder", "file": "zunder.yaml"},
}


# Base plan names
def get_base_plan_name(contract: str) -> str:
    mapping = {
        "ACP Electric": "CEME Base",
        "ACP Electric Sócio": "CEME Sócio",
        "Atlante": "CEME",
        "BlueCharge": "CEME",
        "Charge2Go": "CEME",
        "Chargemap": "CEME",
        "EDP": "CEME",
        "EDP (Bi-horário)": "CEME Bi-horário",
        "EDP Casa": "CEME Casa",
        "EDP Casa (Bi-horário)": "CEME Casa Bi-horário",
        "EDP Casa + UVE": "CEME Casa + UVE",
        "EDP Casa + UVE (Bi-horário)": "CEME Casa + UVE Bi-horário",
        "EDP UVE": "CEME UVE",
        "EDP UVE (Bi-horário)": "CEME UVE Bi-horário",
        "Enable Mobility": "CEME",
        "eVaz Move Base": "CEME Move Base",
        "eVaz Move Volt / Home": "CEME Move Volt / Home",
        "Evio": "CEME",
        "EVPower": "CEME",
        "EZU / AB Energia": "CEME Cartão",
        "EZU / AB Energia App": "CEME App",
        "FactorEnergia": "CEME",
        "Galp Electric": "CEME Base",
        "Galp Electric App + OPC": "CEME App + OPC",
        "Galp Electric Casa + OPC": "CEME Casa + OPC",
        "Galp Electric App": "CEME App",
        "Galp Electric Casa": "CEME Casa",
        "Goldenergy": "CEME Base",
        "Goldenergy Casa": "CEME Casa",
        "Iberdrola": "CEME Base",
        "Iberdrola Casa": "CEME Casa",
        "Meo Energia M4e/M5e": "CEME M4e/M5e",
        "Meo Energia M2e/M3e": "CEME M2e/M3e",
        "Meo Energia Colaboradores": "CEME Colaboradores",
        "Miio": "CEME Base",
        "Miio One": "CEME One",
        "Mobismart/EVCE Active": "CEME Active",
        "Mobismart/EVCE Pré-Pago": "CEME Pré-Pago",
        "Moeve App GOW": "CEME App GOW",
        "Moeve App GOW Deco": "CEME App GOW Deco",
        "Moeve Cartão": "CEME Cartão",
        "Okeana": "CEME",
        "Prio (kWh)": "CEME",
        "Repsol": "CEME",
        "ViaVerde | EcoChoice": "CEME EcoChoice",
        "Zunder": "CEME",
    }
    return mapping.get(contract, f"CEME {contract}")


def get_contract_conditions(cond_str: str) -> list[str]:
    conds = []
    c_lower = cond_str.lower()
    if "cliente casa" in c_lower:
        conds.append("ENERGY_AT_HOME")
    if "associado" in c_lower or "colaboradores" in c_lower or "deco" in c_lower:
        conds.append("PARTNERSHIP")
    if "adesão app" in c_lower:
        conds.append("APP_ACTIVATION")
    if "app mundo" in c_lower or "cashback app" in c_lower:
        conds.append("LOYALTY_PROGRAM")
    return conds


# Custom representer for neat YAML formatting
class CustomDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def str_representer(dumper, data):
    # Enforce quotes around dates or numeric-like strings
    if re.match(r"^\d{4}-\d{2}-\d{2}$", data):
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


CustomDumper.add_representer(str, str_representer)


def main():
    with open(CSV_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Read existing byoe plans to ensure we do not duplicate
    existing_plans_by_provider = {}
    for yf in BYOE_DIR.glob("*.yaml"):
        with open(yf, "r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp)
            if isinstance(data, dict):
                for prov in data.get("providers", []):
                    existing_plans_by_provider[prov["name"]] = [
                        p["name"] for p in prov.get("plans", [])
                    ]

    print("Existing plans in byoe_emsps:")
    for prov_name, plans in existing_plans_by_provider.items():
        print(f"  {prov_name}: {plans}")

    # Group CSV rows by provider file
    file_providers = {}  # filename -> {name, url, updated_at, plans: []}

    for i, r in enumerate(rows):
        contract = r["CEME | CONTRATO"].strip()
        cfg = PROVIDER_MAPPING.get(contract)
        if not cfg:
            print(f"WARNING: Unknown contract '{contract}'")
            continue

        prov_name = cfg["provider"]
        target_file = cfg["file"]

        # Check if entire plan is already present
        # Special cases:
        # ACP Electric: Row 1 & 2 already present
        # Atlante: Row 3 already present
        # EDP: Row 7 (CEME) already present
        if contract in ("ACP Electric", "ACP Electric Sócio", "Atlante", "EDP"):
            print(f"Skipping already added contract: '{contract}' (Row {i + 1})")
            continue

        cond = r["Condicionantes"].strip()
        tarifa = r["Tarifa"].strip()
        ciclo_raw = r["Ciclo"].strip().lower()
        inc_tar = parse_bool(r["Inclui TAR"])
        inc_egme = parse_bool(r["Inclui EGME"])
        inc_iec = parse_bool(r["Inclui IEC"])
        renov = parse_bool(r["Producao Renovavel"])
        ativ = parse_float(r["Ativacao"])
        opc_com = parse_float(r["Comissao OPC %"])
        dt_tar = r["Data Tarifário"].strip() or None
        dt_upd = r["Data atualização"].strip() or None
        dt_fim = r["Data Fim Tarifário"].strip() or None
        func = r["Funcionalidades"].strip()
        mens = parse_float(r["Mensalidade"])
        url = r["URL"].strip() or None

        # Price values
        if inc_tar:
            c_rate = parse_float(r["Cheias / Fora de Vazio (cTAR)"])
            v_rate = parse_float(r["Vazio (cTAR)"])
        else:
            c_rate = parse_float(r["Cheias / Fora de Vazio (sTAR)"])
            v_rate = parse_float(r["Vazio (sTAR)"])

        sched = "1H" if tarifa == "1H" else "2H"

        # Determine cycles to generate
        # If 'ambos', create two plans: one 'diario', one 'semanal'
        # If '?' or 'nenhum' on 2H, assume 'diario'
        if sched == "1H":
            cycles = [None]
        else:
            if ciclo_raw == "ambos":
                cycles = ["diario", "semanal"]
            elif ciclo_raw == "semanal":
                cycles = ["semanal"]
            else:
                cycles = ["diario"]

        base_plan_name = get_base_plan_name(contract)

        # Payment methods
        pm = []
        if "CARD" in func:
            pm.append("RFID_CARD")
        if "APP" in func:
            pm.append("APP")

        # Contract conditions
        cond_list = get_contract_conditions(cond)

        # Notes
        notes = []
        if cond:
            notes.append({"language": "pt", "text": cond})

        # Cost and months
        cost = mens
        months = None
        if mens is not None:
            months = 1
        elif "12 meses" in cond.lower():
            months = 12

        # Networks
        network_entry = {"network_id": "MOBIE"}
        if "postos galp" in cond.lower():
            network_entry["included_cpos"] = ["GLPP"]

        # Generate plans for each cycle
        for cycle_val in cycles:
            if len(cycles) > 1:
                cycle_suffix = " (Diário)" if cycle_val == "diario" else " (Semanal)"
                plan_name = f"{base_plan_name}{cycle_suffix}"
            else:
                plan_name = base_plan_name

            # BYOE section
            byoe_dict = {
                "start_date": dt_tar,
                "schedule": sched,
                "includes_egme": inc_egme,
                "includes_iec": inc_iec,
                "includes_tar": inc_tar,
                "renewable_energy": renov if renov is not None else False,
                "activation_fee": ativ if ativ is not None else 0.0,
            }
            if cycle_val is not None:
                byoe_dict["cycle"] = cycle_val
            if opc_com is not None and opc_com > 0:
                byoe_dict["opc_commission_pct"] = opc_com

            if sched == "1H":
                byoe_dict["all_day"] = c_rate
            else:
                byoe_dict["fora_vazio"] = c_rate
                byoe_dict["vazio"] = v_rate

            plan_dict = {
                "name": plan_name,
                "country_code": "PT",
                "regions": ["PT", "PT::RAA", "PT::RAM"],
                "byoe": byoe_dict,
            }

            if cond_list:
                plan_dict["contract_conditions"] = cond_list
            if cost is not None:
                plan_dict["cost"] = cost
            if months is not None:
                plan_dict["months"] = months
            if dt_fim:
                plan_dict["end_date"] = dt_fim
            if notes:
                plan_dict["notes"] = notes
            if pm:
                plan_dict["payment_methods"] = pm
            plan_dict["networks"] = [network_entry]

            # Register into file_providers
            if target_file not in file_providers:
                file_providers[target_file] = {
                    "provider": prov_name,
                    "url": url,
                    "updated_at": dt_upd,
                    "plans": [],
                }
            else:
                # Update url or updated_at if missing
                if not file_providers[target_file]["url"] and url:
                    file_providers[target_file]["url"] = url
                if dt_upd:
                    cur_upd = file_providers[target_file]["updated_at"]
                    if not cur_upd or dt_upd > cur_upd:
                        file_providers[target_file]["updated_at"] = dt_upd

            file_providers[target_file]["plans"].append(plan_dict)

    print(f"\nTarget files to write/update: {len(file_providers)}")
    total_new_plans = 0

    # Write files
    for filename, pdata in file_providers.items():
        filepath = BYOE_DIR / filename
        prov_name = pdata["provider"]
        new_plans = pdata["plans"]
        total_new_plans += len(new_plans)

        if filepath.exists():
            # Update existing file (e.g. edp.yaml)
            with open(filepath, "r", encoding="utf-8") as fp:
                existing_doc = yaml.safe_load(fp)

            existing_prov = existing_doc["providers"][0]
            existing_plan_names = {p["name"] for p in existing_prov.get("plans", [])}

            # Filter out any duplicates if any
            plans_to_add = [
                p for p in new_plans if p["name"] not in existing_plan_names
            ]
            print(
                f"Updating '{filename}': adding {len(plans_to_add)} plans to existing {len(existing_plan_names)}"
            )
            existing_prov["plans"].extend(plans_to_add)

            # Update updated_at if newer
            if pdata["updated_at"] and (
                not existing_prov.get("updated_at")
                or pdata["updated_at"] > existing_prov["updated_at"]
            ):
                existing_prov["updated_at"] = pdata["updated_at"]

            output_doc = existing_doc
        else:
            # Create new file
            print(
                f"Creating '{filename}': provider '{prov_name}' with {len(new_plans)} plans"
            )
            prov_dict = {
                "name": prov_name,
            }
            if pdata["url"]:
                prov_dict["url"] = pdata["url"]
            if pdata["updated_at"]:
                prov_dict["updated_at"] = pdata["updated_at"]
            prov_dict["plans"] = new_plans
            output_doc = {"providers": [prov_dict]}

        # Save to file
        with open(filepath, "w", encoding="utf-8") as fp:
            yaml.dump(
                output_doc, fp, Dumper=CustomDumper, sort_keys=False, allow_unicode=True
            )

    print(f"\nDone! Added {total_new_plans} plans across {len(file_providers)} files.")


if __name__ == "__main__":
    main()
