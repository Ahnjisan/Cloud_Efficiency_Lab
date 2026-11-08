"""Check a real local Terraform plan without retaining raw plan or state."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from runpy import run_path

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("terraform", type=Path, help="path to Terraform 1.13.5 executable")
    cli = parser.parse_args().terraform.resolve(strict=True)
    helpers = run_path(str(HERE.parent / "004-terraform-evidence/analyze.py"))
    with tempfile.TemporaryDirectory(prefix="infrafit-tf-plan-") as directory:
        root = Path(directory)
        shutil.copy2(HERE / "main.tf", root)
        shutil.copytree(HERE / "fixture", root / "fixture")
        config = root / "isolated.tfrc"
        config.write_text("disable_checkpoint = true\n", encoding="utf-8")
        env = {key: value for key, value in os.environ.items() if not key.upper().startswith("TF_")}
        env.update(TF_CLI_CONFIG_FILE=str(config), TF_IN_AUTOMATION="1", CHECKPOINT_DISABLE="1")

        def command(*args):
            result = subprocess.run([str(cli), *args], cwd=root, env=env, capture_output=True, timeout=45)
            if result.returncode:
                raise RuntimeError(f"Terraform {args[0]} failed with exit code {result.returncode}")
            return result.stdout

        version = json.loads(command("version", "-json"))["terraform_version"]
        assert version == "1.13.5"
        command("init", "-backend=false", "-input=false", "-no-color")
        command("apply", "-auto-approve", "-input=false", "-no-color")
        command("plan", "-refresh=false", "-input=false", "-no-color", "-var=generation=2", "-out=fixture.tfplan")
        plan = json.loads(command("show", "-json", "fixture.tfplan"))

    rejected = helpers["analyze"](plan)
    assert len(rejected) == 2 and all(row["status"] == "unsupported" for row in rejected)
    rows = {}
    for item in plan["resource_changes"]:
        assert item["provider_name"] == "terraform.io/builtin/terraform"
        change = item["change"]
        rows[item["address"]] = {
            "actions": change["actions"],
            "normalized_action": helpers["ACTIONS"][tuple(change["actions"])],
            "selected_after": helpers["fields"](
                change["after"], change["after_sensitive"], change["after_unknown"], ("input", "output", "id")
            ),
        }
    first = rows["module.fixture.terraform_data.replace_first"]
    second = rows["module.fixture.terraform_data.create_first"]
    assert first["actions"] == ["delete", "create"] and second["actions"] == ["create", "delete"]
    assert first["selected_after"]["unavailable"]["input"] == "sensitive"
    assert second["selected_after"]["unavailable"]["output"] == "unknown"
    assert second["selected_after"]["values"]["input"] == "public-fixture-value"
    result = json.dumps({"status": "pass", "terraform_version": version, "format_version": plan["format_version"],
                         "builtin_resources_unsupported_by_aws_extractor": len(rejected), "rows": rows}, indent=2)
    assert "fixture-only-sensitive-value" not in result
    print(result)


if __name__ == "__main__":
    main()
