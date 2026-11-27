import argparse
import datetime
import glob
import os
import sys

import yaml
from pydantic import ValidationError

from .model import TariffDocument
from .regulated_fees import (
    RegulatedFeesDocument,
    TariffSchedule,
    TimeRestrictionsDocument,
)

STALE_CHECK_DAYS = 30


def _parse_iso_date(value: str) -> datetime.date:
    """Parse an ISO 8601 date or datetime string into a date."""
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return datetime.datetime.fromisoformat(value).date()


def _collect_tariff_warnings(
    doc: TariffDocument,
    file_path: str,
    today: datetime.date | None = None,
) -> list[str]:
    """Return non-fatal validation warnings for a TariffDocument."""
    ref_date = today or datetime.datetime.now(datetime.UTC).date()
    warnings_list: list[str] = []

    for prov in doc.providers:
        if not getattr(prov, "publish", True):
            continue

        last_checked = prov.source.last_checked if prov.source else None
        if not last_checked:
            warnings_list.append(
                f"Provider '{prov.name}' in '{file_path}' is missing 'source.last_checked'."
            )
            continue

        try:
            checked_date = _parse_iso_date(last_checked)
        except ValueError:
            warnings_list.append(
                f"Provider '{prov.name}' in '{file_path}' has invalid 'source.last_checked' date '{last_checked}'."
            )
            continue

        days_since_check = (ref_date - checked_date).days
        if days_since_check > STALE_CHECK_DAYS:
            warnings_list.append(
                f"Provider '{prov.name}' in '{file_path}' has not been checked in over a month "
                f"(last_checked: {last_checked}, {days_since_check} days ago)."
            )

    return warnings_list


def _cross_validate_tariff_doc(
    doc: TariffDocument,
    file_path: str,
    today: datetime.date | None = None,
):
    ref_date = today or datetime.datetime.now(datetime.UTC).date()
    for prov in doc.providers:
        if not getattr(prov, "publish", True):
            continue
        for plan in prov.plans:
            if not getattr(plan, "publish", True):
                continue
            if plan.end_date is not None:
                try:
                    end_dt = _parse_iso_date(plan.end_date)
                except ValueError as exc:
                    raise ValueError(
                        f"Plan '{plan.name}' (provider '{prov.name}') in '{file_path}' has invalid end_date '{plan.end_date}'."
                    ) from exc
                if end_dt < ref_date:
                    raise ValueError(
                        f"Plan '{plan.name}' (provider '{prov.name}') in '{file_path}' has lapsed (end_date: {plan.end_date})."
                    )
            if not plan.is_byoe:
                if not plan.networks:
                    raise ValueError(f"Plan '{plan.name}' in '{file_path}' must define at least one network.")
                for net in plan.networks:
                    if not net.tariffs:
                        raise ValueError(
                            f"Network '{net.network_id}' in plan '{plan.name}' ({file_path}) must define at least one tariff."
                        )
            else:
                if not plan.networks:
                    raise ValueError(
                        f"BYOE Plan '{plan.name}' in '{file_path}' must define at least one network (e.g. MOBIE)."
                    )
                has_network_tariffs = any(len(net.tariffs) > 0 for net in plan.networks)
                if not has_network_tariffs and plan.byoe:
                    if plan.byoe.rates_by_voltage:
                        for v_lvl, v_rates in plan.byoe.rates_by_voltage.items():
                            v_name = getattr(v_lvl, "value", str(v_lvl))
                            if plan.byoe.schedule == TariffSchedule.SIMPLES:
                                if (
                                    v_rates.all_day is None
                                    and v_rates.vazio is None
                                    and v_rates.cheias is None
                                    and v_rates.fora_vazio is None
                                ):
                                    raise ValueError(
                                        f"BYOE Plan '{plan.name}' in '{file_path}' with schedule '1H' requires 'all_day' rate in 'byoe:' rates for voltage level '{v_name}'."
                                    )
                            elif plan.byoe.schedule == TariffSchedule.BIHORARIO:
                                if v_rates.vazio is None or (
                                    v_rates.fora_vazio is None and v_rates.cheias is None
                                ):
                                    raise ValueError(
                                        f"BYOE Plan '{plan.name}' in '{file_path}' with schedule '2H' requires 'vazio' and 'cheias' (or 'fora_vazio') rates in 'byoe:' rates for voltage level '{v_name}'."
                                    )
                            elif plan.byoe.schedule == TariffSchedule.TRIHORARIO:
                                if (
                                    v_rates.vazio is None
                                    or v_rates.cheias is None
                                    or v_rates.ponta is None
                                ):
                                    raise ValueError(
                                        f"BYOE Plan '{plan.name}' in '{file_path}' with schedule '3H' requires 'vazio', 'cheias', and 'ponta' rates in 'byoe:' rates for voltage level '{v_name}'."
                                    )
                    else:
                        if plan.byoe.schedule == TariffSchedule.SIMPLES:
                            if (
                                plan.byoe.all_day is None
                                and plan.byoe.vazio is None
                                and plan.byoe.cheias is None
                                and plan.byoe.fora_vazio is None
                            ):
                                raise ValueError(
                                    f"BYOE Plan '{plan.name}' in '{file_path}' with schedule '1H' requires 'all_day' rate in 'byoe:' block."
                                )
                        elif plan.byoe.schedule == TariffSchedule.BIHORARIO:
                            if plan.byoe.vazio is None or (
                                plan.byoe.fora_vazio is None and plan.byoe.cheias is None
                            ):
                                raise ValueError(
                                    f"BYOE Plan '{plan.name}' in '{file_path}' with schedule '2H' requires 'vazio' and 'cheias' (or 'fora_vazio') rates in 'byoe:' block."
                                )
                        elif plan.byoe.schedule == TariffSchedule.TRIHORARIO:
                            if (
                                plan.byoe.vazio is None
                                or plan.byoe.cheias is None
                                or plan.byoe.ponta is None
                            ):
                                raise ValueError(
                                    f"BYOE Plan '{plan.name}' in '{file_path}' with schedule '3H' requires 'vazio', 'cheias', and 'ponta' rates in 'byoe:' block."
                                )


def _validate_file(file_path: str) -> bool:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            print(f"[ERROR] {file_path}: YAML content must be a dictionary")
            return False

        if "regulated_fees" in data:
            RegulatedFeesDocument.model_validate(data)
        elif "time_restrictions_definitions" in data or "time_restrictions" in data:
            TimeRestrictionsDocument.model_validate(data)
        else:
            doc = TariffDocument.model_validate(data)
            _cross_validate_tariff_doc(doc, file_path)
            for warning in _collect_tariff_warnings(doc, file_path):
                print(f"[WARN] {warning}")

        print(f"[OK] {file_path}: Valid")
        return True
    except ValidationError as e:
        print(f"[ERROR] {file_path}: Validation Error")
        for err in e.errors():
            loc = " -> ".join(str(x) for x in err["loc"])
            print(f"  - {loc}: {err['msg']}")
        return False
    except yaml.YAMLError as e:
        print(f"[ERROR] {file_path}: YAML Parsing Error: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] {file_path}: Unexpected Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Validate tariff YAML files.")
    parser.add_argument(
        "paths",
        nargs="*",
        default=[os.path.join("data")],
        help="Files or directories to validate (default: data/)",
    )
    args = parser.parse_args()

    files_to_validate = set()
    for path in args.paths:
        if os.path.isfile(path):
            if path.endswith((".yaml", ".yml")):
                files_to_validate.add(path)
        elif os.path.isdir(path):
            tariffs_path = os.path.join(path, "**", "*.yaml")
            for f in glob.glob(tariffs_path, recursive=True):
                files_to_validate.add(f)

    # Exclude template.yaml from validation as it's a structural reference
    files = sorted(
        [f for f in files_to_validate if "template.yaml" not in os.path.basename(f)]
    )

    if not files:
        print("No YAML files found to validate.")
        return

    errors = False
    for file_path in files:
        if not _validate_file(file_path):
            errors = True

    if errors:
        print("\nSome files failed validation.")
        sys.exit(1)
    else:
        print("\nAll files passed validation successfully.")


if __name__ == "__main__":
    main()
