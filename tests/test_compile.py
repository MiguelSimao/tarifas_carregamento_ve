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
    assert len(data["regulated_fees"]) > 0

    # Verify at least one BYOE plan exists and has generated tariffs with voltage levels and fee types
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
    assert any(t.get("fee_type") == "ENERGY" for t in first_byoe_tariffs)


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
