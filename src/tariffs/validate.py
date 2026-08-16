import argparse
import glob
import os
import sys

import yaml
from pydantic import ValidationError

from .model import TariffDocument
from .regulated_fees import RegulatedFeesDocument, TariffSchedule


def _cross_validate_tariff_doc(doc: TariffDocument, file_path: str):
    for prov in doc.providers:
        for plan in prov.plans:
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
        else:
            doc = TariffDocument.model_validate(data)
            _cross_validate_tariff_doc(doc, file_path)

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
