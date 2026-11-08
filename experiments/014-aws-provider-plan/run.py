"""Generate a real AWS-provider Plan behind a deny-only local endpoint."""
import argparse
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
from runpy import run_path
import shutil
import subprocess
import tempfile
from threading import Thread

HERE = Path(__file__).resolve().parent


@contextmanager
def deny_server():
    attempts = []

    class Deny(BaseHTTPRequestHandler):
        def reject(self):
            attempts.append(self.command)
            self.send_error(403)

        do_CONNECT = do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = do_PATCH = reject

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Deny) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.server_port, attempts
        finally:
            server.shutdown()
            thread.join()


def probe_loopback(port, attempts):
    start = len(attempts)
    statuses = {}
    for method, target in (("GET", "/fixture"), ("CONNECT", "fixture.invalid:443")):
        connection = HTTPConnection("127.0.0.1", port, timeout=3)
        try:
            connection.request(method, target)
            response = connection.getresponse()
            statuses[method] = response.status
            response.read()
        finally:
            connection.close()
    observed = attempts[start:]
    if statuses != {"GET": 403, "CONNECT": 403} or observed != ["GET", "CONNECT"]:
        raise RuntimeError("loopback denial probe failed")
    return {"target": "127.0.0.1", "statuses": statuses, "recorded_methods": observed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("terraform", type=Path, nargs="?")
    parser.add_argument("--check-loopback", action="store_true")
    args = parser.parse_args()
    if args.check_loopback:
        with deny_server() as (port, attempts):
            print(json.dumps(probe_loopback(port, attempts), indent=2))
        return
    if args.terraform is None:
        parser.error("provide a Terraform executable or --check-loopback")
    cli = args.terraform.resolve(strict=True)
    analyze = run_path(str(HERE.parent / "004-terraform-evidence/analyze.py"))["analyze"]
    with tempfile.TemporaryDirectory(prefix="infrafit-aws-plan-") as temp:
        root = Path(temp)
        shutil.copy2(HERE / "main.tf", root)
        config = root / "isolated.tfrc"
        config.write_text("disable_checkpoint = true\n", encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("AWS_", "TF_"))}
        env.update(TF_CLI_CONFIG_FILE=str(config), TF_IN_AUTOMATION="1", CHECKPOINT_DISABLE="1")

        def command(*args, execution_env=env):
            result = subprocess.run([str(cli), *args], cwd=root, env=execution_env,
                                    capture_output=True, timeout=180)
            if result.returncode:
                raise RuntimeError(f"Terraform {args[0]} failed: {result.stderr.decode(errors='replace')}")
            return result.stdout

        version = json.loads(command("version", "-json"))["terraform_version"]
        command("init", "-backend=false", "-input=false", "-no-color")
        lock = (root / ".terraform.lock.hcl").read_text(encoding="utf-8")
        with deny_server() as (port, attempts):
            probe_loopback(port, attempts)
            attempts.clear()
            endpoint = f"http://127.0.0.1:{port}"
            offline_env = {k: v for k, v in env.items() if not k.upper().endswith("_PROXY")}
            offline_env.update(HTTP_PROXY=endpoint, HTTPS_PROXY=endpoint, ALL_PROXY=endpoint,
                               AWS_EC2_METADATA_DISABLED="true")
            command("plan", "-refresh=false", "-input=false", "-no-color",
                    f"-var=blocked_endpoint={endpoint}", "-out=fixture.tfplan", execution_env=offline_env)
            plan = json.loads(command("show", "-json", "fixture.tfplan", execution_env=offline_env))

    rows = {row["address"]: row for row in analyze(plan)}
    assert rows["aws_instance.fixture"]["after"]["values"] == {"instance_type": "t3.micro"}
    assert rows["aws_ebs_volume.fixture"]["after"]["values"] == {
        "type": "gp3", "size": 20, "iops": 3000, "throughput": 125,
    }
    assert rows["aws_instance.masked"]["after"]["unavailable"] == {"instance_type": "sensitive"}
    assert rows["aws_ebs_volume.unknown"]["after"]["unavailable"] == {"size": "unknown"}
    assert all(rows[address]["action"] == "create" for address in rows if address.startswith("aws_"))
    assert re.search(r'(?m)^\s*version\s*=\s*"5\.100\.0"$', lock), "unexpected provider version"
    if attempts:
        raise RuntimeError(f"local deny endpoint received {len(attempts)} provider request(s)")
    result = json.dumps({"status": "pass", "terraform_version": version, "provider_version": "5.100.0",
                         "format_version": plan["format_version"], "denied_requests": len(attempts),
                         "rows": rows}, indent=2)
    assert "fixture-only-user-data" not in result and "t3.nano" not in result
    print(result)


if __name__ == "__main__":
    main()
