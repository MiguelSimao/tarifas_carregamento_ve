import glob
import json
import os

import yaml

from tariffs.compile import main as compile_main
from tariffs.validate import _validate_file


def test_pt_tariff_files_valid():
    """Ensure all Portugal tariff YAML files (including subdirectories) pass validation."""
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "pt")
    assert os.path.exists(data_dir), "data/pt directory missing"

    yaml_files = glob.glob(os.path.join(data_dir, "**", "*.yaml"), recursive=True)
    assert len(yaml_files) > 0, "No YAML files found in data/pt"

    for file_path in yaml_files:
        assert _validate_file(file_path), f"File failed validation: {file_path}"


def test_compilation_output(tmp_path):
    """Test compiling YAML files into a master JSON output including BYOE & regulated fees."""
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "pt")
    output_file = str(tmp_path / "_master.json")

    # Simulate command line arguments
    import sys

    orig_argv = sys.argv
    try:
        sys.argv = ["tariffs-compile", "-i", data_dir, "-o", output_file]
        compile_main()
    finally:
        sys.argv = orig_argv

    assert os.path.exists(output_file)
    with open(output_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "providers" in data
    assert len(data["providers"]) > 0
    assert "regulated_fees" in data
    assert len(data["regulated_fees"]) >= 3
    rf_countries = [rf["country_code"] for rf in data["regulated_fees"]]
    assert "PT" in rf_countries
    assert "PT::RAA" in rf_countries
    assert "PT::RAM" in rf_countries

    # Verify at least one BYOE plan exists and has generated tariffs with voltage levels & time restrictions
    byoe_plans = [
        plan
        for p in data["providers"]
        for plan in p["plans"]
        if plan.get("byoe") is not None
    ]
    assert len(byoe_plans) > 0, "No BYOE plan found in compilation output"
    first_byoe_tariffs = byoe_plans[0]["networks"][0]["tariffs"]
    assert len(first_byoe_tariffs) > 0
    assert any(t.get("mobie_voltage_level") in ("BT", "MT") for t in first_byoe_tariffs)
    assert any("time_restrictions" in t for t in first_byoe_tariffs)
    tariffs_with_restrs = [t for t in first_byoe_tariffs if "time_restrictions" in t]
    assert all(
        all(r.get("name") in ("vazio", "fora_vazio", "cheias", "ponta") for r in t["time_restrictions"])
        for t in tariffs_with_restrs
    )
    assert not any("tou_period" in t for t in first_byoe_tariffs)


def test_provider_merging_and_conflict_detection(tmp_path):
    """Test merging plans for the same provider across files and conflict detection."""
    import sys

    import pytest

    dir_path = tmp_path / "yaml_dir"
    dir_path.mkdir()

    file1 = dir_path / "provider1.yaml"
    file1.write_text(
        yaml.dump(
            {
                "providers": [
                    {
                        "name": "SharedProvider",
                        "url": "https://example.com",
                        "plans": [
                            {
                                "name": "PlanA",
                                "byoe": False,
                                "networks": [
                                    {"network_id": "NET1", "tariffs": [{"price": 0.3}]}
                                ],
                            }
                        ],
                    }
                ]
            }
        )
    )

    file2 = dir_path / "provider2.yaml"
    file2.write_text(
        yaml.dump(
            {
                "providers": [
                    {
                        "name": "SharedProvider",
                        "url": "https://example.com",
                        "plans": [
                            {
                                "name": "PlanB",
                                "byoe": {
                                    "cycle": "diario",
                                    "includes_tar": False,
                                },
                                "networks": [
                                    {"network_id": "NET1", "tariffs": [{"price": 0.2}]}
                                ],
                            }
                        ],
                    }
                ]
            }
        )
    )

    output_file = str(tmp_path / "merged_master.json")
    orig_argv = sys.argv
    try:
        sys.argv = ["tariffs-compile", "-i", str(dir_path), "-o", output_file]
        compile_main()
    finally:
        sys.argv = orig_argv

    with open(output_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data["providers"]) == 1
    shared = data["providers"][0]
    assert shared["name"] == "SharedProvider"
    assert len(shared["plans"]) == 2
    plan_names = [p["name"] for p in shared["plans"]]
    assert "PlanA" in plan_names
    assert "PlanB" in plan_names

    # Now test conflict in provider metadata url
    file3 = dir_path / "provider3.yaml"
    file3.write_text(
        yaml.dump(
            {
                "providers": [
                    {
                        "name": "SharedProvider",
                        "url": "https://conflicting-url.com",
                        "plans": [
                            {
                                "name": "PlanC",
                                "networks": [
                                    {"network_id": "NET1", "tariffs": [{"price": 0.4}]}
                                ],
                            }
                        ],
                    }
                ]
            }
        )
    )

    try:
        sys.argv = ["tariffs-compile", "-i", str(dir_path), "-o", output_file]
        with pytest.raises(SystemExit):
            compile_main()
    finally:
        sys.argv = orig_argv


def test_compiler_driven_multi_region_expansion():
    """Verify that multi-region BYOE plans expand into distinct regional plans with appropriate TAR and time restrictions."""
    with open("data/tariffs_master.json", "r", encoding="utf-8") as f:
        master = json.load(f)

    acp_provider = next(p for p in master["providers"] if p["name"] == "ACP Electric")
    ceme_base_plans = [pl for pl in acp_provider["plans"] if pl["name"] == "CEME Base"]

    # Verify 3 distinct plans generated: PT, PT::RAA, PT::RAM
    regional_codes = {pl["country_code"] for pl in ceme_base_plans}
    assert regional_codes == {"PT", "PT::RAA", "PT::RAM"}

    # Verify Continental plan has PT TAR rates, 22:00-08:00 Vazio, and 23% VAT
    pt_plan = next(pl for pl in ceme_base_plans if pl["country_code"] == "PT")
    assert pt_plan.get("vat") == 0.23
    assert pt_plan.get("includes_vat") is False
    pt_vazio_tar = next(
        t for t in pt_plan["networks"][0]["tariffs"]
        if t.get("mobie_fee_type") == "TAR" and t.get("price") == 0.0266
    )
    assert pt_vazio_tar["time_restrictions"][0]["start_time"] == "22:00"
    assert pt_vazio_tar["time_restrictions"][0]["end_time"] == "08:00"

    # Verify Madeira plan has RAM TAR rates, 23:00-09:00 Vazio, and 22% VAT
    ram_plan = next(pl for pl in ceme_base_plans if pl["country_code"] == "PT::RAM")
    assert ram_plan.get("vat") == 0.22
    assert ram_plan.get("includes_vat") is False
    ram_vazio_tar = next(
        t for t in ram_plan["networks"][0]["tariffs"]
        if t.get("mobie_fee_type") == "TAR" and t.get("price") == 0.0905
    )
    assert ram_vazio_tar["time_restrictions"][0]["start_time"] == "23:00"
    assert ram_vazio_tar["time_restrictions"][0]["end_time"] == "09:00"

    # Verify Azores plan has RAA TAR rates, 22:00-08:00 Vazio, and 16% VAT
    raa_plan = next(pl for pl in ceme_base_plans if pl["country_code"] == "PT::RAA")
    assert raa_plan.get("vat") == 0.16
    assert raa_plan.get("includes_vat") is False
    raa_vazio_tar = next(
        t for t in raa_plan["networks"][0]["tariffs"]
        if t.get("mobie_fee_type") == "TAR" and t.get("price") == 0.0905
    )
    assert raa_vazio_tar["time_restrictions"][0]["start_time"] == "22:00"
    assert raa_vazio_tar["time_restrictions"][0]["end_time"] == "08:00"

