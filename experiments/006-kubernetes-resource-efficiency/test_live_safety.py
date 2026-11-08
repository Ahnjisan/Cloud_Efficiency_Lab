"""Regression checks using saved measurements and fake subprocesses."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
import os
from pathlib import Path
from runpy import run_path
import subprocess
import sys
import unittest
from unittest.mock import patch

from live_safety import cleanup_owned, pin_local_docker, validate_measurement

HERE = Path(__file__).resolve().parent
DOCKER = HERE.parent / "005-container-resource-efficiency"
LOCAL = "npipe:////./pipe/dockerDesktopLinuxEngine"


class LiveSafetyTest(unittest.TestCase):
    def test_rejects_remote_context_and_host(self):
        with self.assertRaisesRegex(RuntimeError, "DOCKER_HOST"):
            pin_local_docker(self.fail, {"DOCKER_HOST": "ssh://remote"})
        with self.assertRaisesRegex(RuntimeError, "local Windows named pipe"):
            pin_local_docker(lambda args: "tcp://remote:2375" if "inspect" in args else "remote", {})

    def test_pins_local_context_and_clears_overrides(self):
        env = {"DOCKER_CONTEXT": "desktop-linux", "DOCKER_TLS_VERIFY": "1", "PATH": "example"}
        pinned = pin_local_docker(lambda args: LOCAL if "inspect" in args else "desktop-linux", env)
        self.assertEqual(pinned, {"DOCKER_HOST": LOCAL, "PATH": "example"})
        self.assertEqual(env["DOCKER_CONTEXT"], "desktop-linux")

    def test_cleanup_finds_unacknowledged_network_and_minikube_helpers(self):
        profile = "infrafit-example"
        present = {
            "network": {"net-id": {"label=infrafit.run=" + profile}},
            "volume": {profile: {"label=name.minikube.sigs.k8s.io=" + profile}},
            "container": {
                "other": {"label=name.minikube.sigs.k8s.io=existing"},
                "sidecar": {"label=name.minikube.sigs.k8s.io=" + profile},
                "extractor": {"volume=" + profile},
            },
        }
        removals = []

        def command(args, **kwargs):
            if "rm" in args:
                kind = args[1]
                for name in args[3:]:
                    if name != "-f":
                        del present[kind][name]
                        removals.append(name)
                return ""
            kind = "container" if args[1] == "ps" else args[1]
            return "\n".join(name for name, selectors in present[kind].items() if args[-1] in selectors)

        with patch("live_safety.time.sleep"):
            self.assertTrue(cleanup_owned(command, profile, minikube=True))
        self.assertEqual(removals, ["extractor", "sidecar", profile, "net-id"])
        self.assertEqual(set(present["container"]), {"other"})

    def test_cleanup_fails_closed_on_unowned_residual_or_listing_error(self):
        def unowned(args, **kwargs):
            self.assertNotIn("rm", args)
            return "unowned-id" if args[-1].startswith("name=") else ""

        def unavailable(args, **kwargs):
            raise RuntimeError("daemon unavailable")

        with patch("live_safety.time.sleep"):
            self.assertFalse(cleanup_owned(unowned, "scope"))
            self.assertFalse(cleanup_owned(unavailable, "scope"))

    def test_both_runners_clean_up_when_network_create_times_out(self):
        self.check_create_interruption(memory_error=False)

    def test_both_runners_wait_before_cleanup_when_memory_read_fails(self):
        self.check_create_interruption(memory_error=True)

    def test_both_runners_report_unconfirmed_termination(self):
        self.check_create_interruption(memory_error=True, wait_timeout=True)

    def check_create_interruption(self, memory_error, wait_timeout=False):
        for directory in (DOCKER, HERE):
            with self.subTest(runner=directory.name):
                main = run_path(str(directory / "run_live.py"))["main"]
                network = set()
                commands = []
                lifecycle = []
                test = self

                def memory():
                    if memory_error and network:
                        raise OSError("Windows memory reading failed")
                    return 5

                main.__globals__["memory"] = memory

                class FakeProcess:
                    def __init__(self, args, **kwargs):
                        commands.append(args)
                        self.returncode = 0
                        self.output = ""
                        self.timed_out = False
                        if args[:3] == ["docker", "context", "show"]:
                            self.output = "desktop-linux"
                        elif args[:3] == ["docker", "context", "inspect"]:
                            self.output = LOCAL
                        else:
                            if args[0] == "docker":
                                test.assertEqual(kwargs["env"]["DOCKER_HOST"], LOCAL)
                                test.assertNotIn("DOCKER_CONTEXT", kwargs["env"])
                            if args[:3] == ["docker", "network", "create"]:
                                network.add("experiment-net")
                                self.timed_out = True
                            elif args[:3] == ["docker", "network", "ls"]:
                                self.output = "\n".join(network)
                            elif args[:3] == ["docker", "network", "rm"]:
                                lifecycle.append("remove")
                                network.remove(args[-1])

                    def communicate(self, **kwargs):
                        if self.timed_out:
                            raise subprocess.TimeoutExpired("docker network create", 2)
                        return self.output.encode(), b""

                    def kill(self):
                        lifecycle.append("kill")
                        self.timed_out = False
                        self.returncode = 124

                    def wait(self, **kwargs):
                        lifecycle.append("wait")
                        if wait_timeout:
                            raise subprocess.TimeoutExpired("docker network create", 5)
                        test.assertFalse(self.timed_out)
                        return self.returncode

                output = io.StringIO()
                with patch("subprocess.Popen", FakeProcess), patch("time.sleep"), redirect_stdout(output), \
                     patch("time.monotonic", side_effect=iter(range(0, 3000, 100))), \
                     patch.object(Path, "rglob", return_value=()), \
                     patch.dict(os.environ, {"DOCKER_HOST": "", "DOCKER_CONTEXT": "desktop-linux"}), \
                     patch.object(sys, "argv", ["run_live.py"]):
                    self.assertEqual(main(), 1)
                result = json.loads(output.getvalue())
                if wait_timeout:
                    self.assertEqual(result["status"], "fail")
                    self.assertFalse(result["cleanup_verified"])
                    self.assertIn("termination could not be verified", result["cleanup_reason"])
                    self.assertEqual(lifecycle, ["kill", "wait"])
                    self.assertTrue(network)
                    continue
                self.assertEqual(result["status"], "blocked")
                self.assertTrue(result["cleanup_verified"])
                self.assertEqual(lifecycle, ["kill", "wait", "remove"])
                if memory_error:
                    self.assertIn("memory reading failed", result["reason"])
                self.assertFalse(network)
                self.assertFalse(any(args[0] == "minikube" for args in commands))

    def test_saved_measurements_and_invalid_variants(self):
        for path in (DOCKER / "live-result.json", HERE / "live-attempt-4.json"):
            for run in json.loads(path.read_text(encoding="utf-8"))["runs"]:
                mcpu = run["limit_m"] if "limit_m" in run else int(float(run["cpu"]) * 1000)
                with self.subTest(log=path.name, mcpu=mcpu):
                    validate_measurement(run, mcpu)
                    self.assertTrue(run.pop("measurement_valid"))
                    self.assertFalse(run.pop("target_load_met"))

                    for case in ("no successes", "wrong quota", "missing counter", "nonfinite latency"):
                        invalid = deepcopy(run)
                        invalid["measurement_valid"] = False
                        if case == "no successes":
                            invalid["k6"]["metrics"]["successful_requests"]["count"] = 0
                        elif case == "wrong quota":
                            invalid["after"]["cpu.max"] = "200000 100000"
                        elif case == "missing counter":
                            del invalid["before"]["cpu.stat"]
                        else:
                            invalid["k6"]["metrics"]["http_req_duration"]["p(99)"] = float("nan")
                        with self.subTest(case=case), self.assertRaises(ValueError):
                            validate_measurement(invalid, mcpu)
                        self.assertFalse(invalid["measurement_valid"])

    def test_http_failure_rate_cannot_contradict_success_count(self):
        run = json.loads((DOCKER / "live-result.json").read_text(encoding="utf-8"))["runs"][0]
        metrics = run["k6"]["metrics"]
        metrics["successful_requests"]["count"] = metrics["http_reqs"]["count"] = 750
        metrics["http_req_failed"] = {"value": 0.5, "passes": 375, "fails": 375}
        with self.assertRaisesRegex(ValueError, "HTTP failure rate contradicts"):
            validate_measurement(run, 1000)
        self.assertNotIn("measurement_valid", run)


if __name__ == "__main__":
    unittest.main()
