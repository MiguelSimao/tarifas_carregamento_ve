import json
import os

import yaml

from tariffs.compile import main as compile_main
from tariffs.validate import _validate_file


def test_pt_tariff_files_valid():
    """Ensure all Portugal tariff YAML files pass validation."""
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "pt")
    assert os.path.exists(data_dir), "data/pt directory missing"

    yaml_files = [
        os.path.join(data_dir, f)
        for f in os.listdir(data_dir)
        if f.endswith((".yaml", ".yml"))
    ]
    assert len(yaml_files) > 0, "No YAML files found in data/pt"

    for file_path in yaml_files:
        assert _validate_file(file_path), f"File failed validation: {file_path}"


def test_compilation_output(tmp_path):
    """Test compiling YAML files into a master JSON output."""
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
