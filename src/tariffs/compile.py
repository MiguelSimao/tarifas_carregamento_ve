import argparse
import glob
import os
import sys

import yaml

from .model import Provider, TariffDocument
from .regulated_fees import RegulatedFeesDocument
from .validate import _cross_validate_tariff_doc

DEFAULT_OUTPUT_PATH = os.path.join("data", "tariffs_master.json")


def main():
    parser = argparse.ArgumentParser(
        description="Compile multiple tariff YAML files into a master JSON file."
    )
    parser.add_argument(
        "-i",
        "--input",
        nargs="*",
        default=[os.path.join("data")],
        help="Files or directories to compile (default: data/)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        help=f"Path for the output master JSON file (default: {DEFAULT_OUTPUT_PATH})",
    )
    args = parser.parse_args()

    files_to_compile = set()
    for path in args.input:
        if os.path.isfile(path):
            if path.endswith((".yaml", ".yml")):
                files_to_compile.add(path)
        elif os.path.isdir(path):
            tariffs_path = os.path.join(path, "**", "*.yaml")
            for f in glob.glob(tariffs_path, recursive=True):
                files_to_compile.add(f)

    # Exclude template.yaml from compilation as it's a structural reference
    files = sorted(
        [f for f in files_to_compile if "template.yaml" not in os.path.basename(f)]
    )

    if not files:
        print("No YAML files found to compile.")
        sys.exit(1)

    raw_providers = []
    master_regulated_fees = []
    errors = False

    for file_path in files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict):
                raise ValueError("YAML content must be a dictionary")

            if "regulated_fees" in data:
                fees_doc = RegulatedFeesDocument.model_validate(data)
                master_regulated_fees.extend(fees_doc.regulated_fees)
            else:
                doc = TariffDocument.model_validate(data)
                _cross_validate_tariff_doc(doc, file_path)
                for prov in doc.providers:
                    raw_providers.append((file_path, prov))

            print(f"[OK] Read {file_path}")
        except Exception as e:
            print(f"[ERROR] Failed to process {file_path}: {e}")
            errors = True

    if errors:
        print("\nCompilation aborted due to validation or parsing errors.")
        sys.exit(1)

    # Merge providers by name across files and check for metadata conflicts
    merged_providers_dict = {}
    provider_sources = {}

    for file_path, prov in raw_providers:
        name = prov.name
        if name not in merged_providers_dict:
            merged_providers_dict[name] = Provider(
                name=prov.name,
                url=prov.url,
                updated_at=prov.updated_at,
                plans=list(prov.plans),
            )
            provider_sources[name] = [file_path]
        else:
            existing = merged_providers_dict[name]
            sources = provider_sources[name]

            # Check url conflict
            if prov.url is not None:
                if existing.url is not None and existing.url != prov.url:
                    print(
                        f"[ERROR] Conflict for provider '{name}': field 'url' differs "
                        f"between '{sources[0]}' ({existing.url}) and '{file_path}' ({prov.url})"
                    )
                    errors = True
                elif existing.url is None:
                    existing.url = prov.url

            # Check updated_at conflict
            if prov.updated_at is not None:
                if (
                    existing.updated_at is not None
                    and existing.updated_at != prov.updated_at
                ):
                    print(
                        f"[ERROR] Conflict for provider '{name}': field 'updated_at' differs "
                        f"between '{sources[0]}' ({existing.updated_at}) and '{file_path}' ({prov.updated_at})"
                    )
                    errors = True
                elif existing.updated_at is None:
                    existing.updated_at = prov.updated_at

            existing.plans.extend(prov.plans)
            sources.append(file_path)

    if errors:
        print("\nCompilation aborted due to metadata conflicts across provider files.")
        sys.exit(1)

    master_providers = list(merged_providers_dict.values())

    # Create the master document
    master_doc = TariffDocument(
        providers=master_providers,
        regulated_fees=master_regulated_fees if master_regulated_fees else None,
    )

    # Ensure output directory exists
    output_dir = os.path.dirname(os.path.abspath(args.output))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Dump the master document to JSON
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(master_doc.model_dump_json(indent=2, exclude_none=True) + "\n")

    print(f"\nSuccessfully compiled {len(files)} files into {args.output}")


if __name__ == "__main__":
    main()
