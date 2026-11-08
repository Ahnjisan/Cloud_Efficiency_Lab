"""Regenerate the local InfraFit experiment outputs in dependency order."""
import datetime
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
RUNS = (
    ("001", "001-ebs-waste-rules/verify_rules.py", "001-reproduction.stdout.txt"),
    ("002", "002-ebs-rule-robustness/evaluate.py", "002-ebs-rule-robustness/result.json"),
    ("003", "003-aws-cost-simulation/simulate.py", "003-aws-cost-simulation/result.json"),
    ("004", "004-terraform-evidence/analyze.py", "004-terraform-evidence/result.json"),
    ("006", "006-kubernetes-resource-efficiency/placement.py", "006-kubernetes-resource-efficiency/result.json"),
    ("007", "007-infrafit-feasibility/integrate.py", "007-infrafit-feasibility/result.json"),
    ("008", "008-evidence-reconciliation/reconcile.py", "008-evidence-reconciliation/result.json"),
    ("009", "009-ebs-review-cost/evaluate.py", "009-ebs-review-cost/result.json"),
    ("010", "010-cpu-quality-envelope/analyze.py", "010-cpu-quality-envelope/result.json"),
    ("011", "011-cost-quality-sensitivity/simulate.py", "011-cost-quality-sensitivity/result.json"),
)

def digest(content):
    return hashlib.sha256(content).hexdigest()

def main():
    log_path = ROOT / "infrafit-execution-log.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else {"runs": []}
    for experiment, script, output in RUNS:
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        run = subprocess.run(
            [sys.executable, "-B", str(ROOT / script)],
            cwd=REPO, capture_output=True, timeout=30,
        )
        destination = ROOT / output
        if run.returncode == 0:
            previous = destination.read_bytes() if destination.exists() else None
            if previous is not None and previous != run.stdout:
                for older in log["runs"]:
                    if older.get("stdout_path") == output:
                        older["stdout_path"] = None
                        older["superseded_stdout_sha256"] = digest(previous)
            destination.write_bytes(run.stdout)
        log["runs"].append({
            "id": experiment, "command": f"py -3 -B experiments/{script}",
            "platform": platform.platform(), "python": platform.python_version(),
            "started_utc": started, "exit_code": run.returncode,
            "stdout_path": output if run.returncode == 0 else None,
            "stdout_sha256": digest(run.stdout),
            "stderr": run.stderr.decode("utf-8", errors="replace").replace(str(REPO), "[repository]"),
            "failed_stdout": run.stdout.decode("utf-8", errors="replace").replace(str(REPO), "[repository]") if run.returncode else None,
        })
        log_path.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")
        print(f"{experiment}: exit {run.returncode}")
        if run.returncode:
            return run.returncode
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
