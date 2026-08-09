import argparse
import json
import os

from .model import TariffDocument

DEFAULT_SCHEMA_PATH = os.path.join("data", "tariffs_schema.json")


def main():
    parser = argparse.ArgumentParser(
        description="Generate JSON schema for TariffDocument Pydantic model."
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_SCHEMA_PATH,
        help=f"Path for the output JSON schema file (default: {DEFAULT_SCHEMA_PATH})",
    )
    args = parser.parse_args()

    schema = TariffDocument.model_json_schema()

    output_dir = os.path.dirname(os.path.abspath(args.output))
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
        f.write("\n")

    print(f"Successfully generated JSON schema at {args.output}")


if __name__ == "__main__":
    main()
