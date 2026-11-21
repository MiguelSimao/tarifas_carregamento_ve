"""Tests for the legacy CEME comparison CSV exporter."""

import csv
import os
import sys

from tariffs.compile import main as compile_main
from tariffs.legacy.byoe_exporter import (
    export_byoe_to_csv,
    format_eu_number,
    resolve_contract_name,
)
from tariffs.model import (
    ByoeConfig,
    MobieVoltageLevel,
    PaymentMethod,
    Plan,
    Provider,
)
from tariffs.regulated_fees import (
    RegulatedFees,
    TariffSchedule,
    TarPeriodRate,
    TarVariant,
)


def test_format_eu_number():
    assert format_eu_number(None) == ""
    assert format_eu_number(0.15, decimals=4) == "0,1500"
    assert format_eu_number(0.2892, decimals=3) == "0,289"
    assert format_eu_number(3.99, decimals=2) == "3,99"
    assert format_eu_number(0.1, decimals=5) == "0,10000"


def test_resolve_contract_name():
    assert resolve_contract_name("EDP", "CEME") == "EDP"
    assert resolve_contract_name("EDP", "CEME Bi-horário") == "EDP (Bi-horário)"
    assert resolve_contract_name("Galp", "CEME Base") == "Galp Electric"
    assert resolve_contract_name("Unknown", "CEME Custom") == "Unknown Custom"
    assert resolve_contract_name("Unknown", "CEME") == "Unknown"


def test_byoe_exporter_calculations(tmp_path):
    output_file = str(tmp_path / "test_legacy.csv")

    reg_fees = [
        RegulatedFees(
            country_code="PT",
            effective_date="2026-01-01",
            vat=0.23,
            iec=0.0010,
            egme_connection=0.1088,
            tar_variants=[
                TarVariant(
                    voltage_level=MobieVoltageLevel.BT,
                    schedule=TariffSchedule.BIHORARIO,
                    rates=[
                        TarPeriodRate(period="cheias", rate=0.1192),
                        TarPeriodRate(period="vazio", rate=0.0266),
                    ],
                ),
                TarVariant(
                    voltage_level=MobieVoltageLevel.MT,
                    schedule=TariffSchedule.BIHORARIO,
                    rates=[
                        TarPeriodRate(period="cheias", rate=0.0812),
                        TarPeriodRate(period="vazio", rate=0.0157),
                    ],
                ),
            ],
        )
    ]

    provider1 = Provider(
        name="ProviderWithoutTar",
        url="https://example.com/no-tar",
        updated_at="2026-01-01",
        plans=[
            Plan(
                name="CEME (Diário)",
                country_code="PT",
                payment_methods=[PaymentMethod.RFID_CARD, PaymentMethod.APP],
                byoe=ByoeConfig(
                    schedule=TariffSchedule.BIHORARIO,
                    cycle="diario",
                    includes_tar=False,
                    includes_egme=False,
                    includes_iec=False,
                    activation_fee=0.1500,
                    fora_vazio=0.1690,
                    vazio=0.1690,
                ),
            ),
            Plan(
                name="CEME (Semanal)",
                country_code="PT",
                payment_methods=[PaymentMethod.RFID_CARD, PaymentMethod.APP],
                byoe=ByoeConfig(
                    schedule=TariffSchedule.BIHORARIO,
                    cycle="semanal",
                    includes_tar=False,
                    includes_egme=False,
                    includes_iec=False,
                    activation_fee=0.1500,
                    fora_vazio=0.1690,
                    vazio=0.1690,
                ),
            ),
        ],
    )

    provider2 = Provider(
        name="ProviderWithTar",
        url="https://example.com/with-tar",
        updated_at="2026-01-01",
        plans=[
            Plan(
                name="CEME",
                country_code="PT",
                payment_methods=[PaymentMethod.RFID_CARD],
                byoe=ByoeConfig(
                    schedule=TariffSchedule.SIMPLES,
                    includes_tar=True,
                    includes_egme=False,
                    includes_iec=False,
                    activation_fee=0.0,
                    all_day=0.2000,
                ),
            )
        ],
    )

    export_byoe_to_csv(
        providers=[provider1, provider2],
        regulated_fees=reg_fees,
        output_path=output_file,
        reference_date="2026-01-01",
    )

    assert os.path.exists(output_file)
    with open(output_file, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    # Check single header row
    assert len(rows) == 1 + 2  # 1 header row + 2 grouped entries
    assert rows[0][0] == "CEME | CONTRATO"
    assert len(rows[0]) == 34

    # ProviderWithoutTar merged daily and weekly into Ambos
    row_no_tar = next(r for r in rows[1:] if "ProviderWithoutTar" in r[0])
    assert row_no_tar[8] == "Ambos"  # Ciclo
    assert row_no_tar[11] == "FALSE"  # Inclui TAR
    assert row_no_tar[18] == "0,1690"  # Cheias sTAR
    assert row_no_tar[19] == "0,1690"  # Vazio sTAR
    assert row_no_tar[20] == "CARD, APP"  # Funcionalidades

    # BT estimated: Cheias = 0.1690 + 0.1192 + 0.0010 = 0.289
    assert row_no_tar[27] == "0,289"
    # BT estimated: Vazio = 0.1690 + 0.0266 + 0.0010 = 0.197
    assert row_no_tar[28] == "0,197"
    # MT estimated: Cheias = 0.1690 + 0.0812 + 0.0010 = 0.251
    assert row_no_tar[30] == "0,251"
    # MT estimated: Vazio = 0.1690 + 0.0157 + 0.0010 = 0.186
    assert row_no_tar[31] == "0,186"

    # ProviderWithTar with simple schedule
    row_with_tar = next(r for r in rows[1:] if "ProviderWithTar" in r[0])
    assert row_with_tar[7] == "1H"
    assert row_with_tar[8] == "Nenhum"
    assert row_with_tar[11] == "TRUE"
    assert row_with_tar[15] == "0,2000"  # Cheias cTAR
    assert row_with_tar[16] == "0,2000"  # Vazio cTAR
    # With TAR BT: 0.2000 + 0.0010 = 0.201
    assert row_with_tar[27] == "0,201"
    assert row_with_tar[28] == "0,201"

    # Check ranking column (1 and 2)
    ranks = [r[33] for r in rows[1:]]
    assert ranks == ["1", "2"]


def test_compile_legacy_csv_generation(tmp_path):
    data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "pt")
    output_json = str(tmp_path / "tariffs_master.json")
    output_csv = str(tmp_path / "tariffs_legacy_ceme_master.csv")

    orig_argv = sys.argv
    try:
        sys.argv = [
            "tariffs-compile",
            "-i",
            data_dir,
            "-o",
            output_json,
            "--legacy-csv-output",
            output_csv,
        ]
        compile_main()
    finally:
        sys.argv = orig_argv

    assert os.path.exists(output_json)
    assert os.path.exists(output_csv)

    with open(output_csv, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert len(rows) > 1
    assert rows[0][0] == "CEME | CONTRATO"
    for r in rows:
        assert len(r) == 34


def test_compile_no_legacy_csv(tmp_path):
    data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data", "pt")
    output_json = str(tmp_path / "tariffs_master.json")
    output_csv = str(tmp_path / "tariffs_legacy_ceme_master.csv")

    orig_argv = sys.argv
    try:
        sys.argv = [
            "tariffs-compile",
            "-i",
            data_dir,
            "-o",
            output_json,
            "--legacy-csv-output",
            output_csv,
            "--no-legacy-csv",
        ]
        compile_main()
    finally:
        sys.argv = orig_argv

    assert os.path.exists(output_json)
    assert not os.path.exists(output_csv)
