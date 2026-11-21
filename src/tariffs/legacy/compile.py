"""Legacy CEME compilation and CSV export."""

from __future__ import annotations

import os

from tariffs.legacy.byoe_exporter import export_byoe_to_csv
from tariffs.model import Provider
from tariffs.regulated_fees import RegulatedFees

DEFAULT_LEGACY_CSV_OUTPUT_PATH = os.path.join("data", "tariffs_legacy_ceme_master.csv")


def compile_legacy_ceme_csv(
    providers: list[Provider],
    regulated_fees: list[RegulatedFees] | None,
    output_path: str = DEFAULT_LEGACY_CSV_OUTPUT_PATH,
    reference_date: str | None = None,
) -> str:
    """Compile published BYOE plans into the legacy CEME comparison CSV format."""
    out_file = export_byoe_to_csv(
        providers=providers,
        regulated_fees=regulated_fees,
        output_path=output_path,
        reference_date=reference_date,
    )
    print(f"[OK] Exported legacy CEME comparison CSV to {out_file}")
    return out_file
