"""Tests for the --report option (infrafit/report.py) with synthetic inputs only."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
CLI = HERE / "cli.py"
WL = [str(HERE / "workloads.json"), str(HERE / "workloads-ops.json")]


def cli(*args):
    return subprocess.run([sys.executable, "-B", str(CLI), *args], capture_output=True, text=True, encoding="utf-8",
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"})


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def report(self, name, workloads=WL, *extra):
        path = self.dir / name
        r = cli("--workloads", *workloads, "--report", str(path), *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return path.read_text(encoding="utf-8"), r

    def test_summary_counts_match_json(self):
        data = json.loads(cli("--workloads", *WL, "--json").stdout)
        text, _ = self.report("r.md")
        for group, rows in (("EC2·EBS 판정", data["decisions"]), ("워크로드 규칙", data["workload_decisions"])):
            counts = [sum(1 for d in rows if d["decision"] == s) for s in ("candidate", "keep", "hold")]
            self.assertIn(f"| {group} | {counts[0]} | {counts[1]} | {counts[2]} |", text)

    def test_required_sections_and_notices(self):
        for name in ("r.md", "r.html"):
            text, _ = self.report(name)
            for needle in ("예상 절감은 실제 청구 절감이 아닙니다", "실제 청구 대사: 미검증", "요약", "규칙별", "항목별",
                           "판단 보류 사유", "비용 급증 조사 대기열", "사용한 기준값", "입력 데이터"):
                self.assertIn(needle, text, (name, needle))
            for level in ("실험 확인", "공식 자료", "임시값"):
                self.assertIn(level, text)

    def test_savings_with_different_basis_are_not_added(self):
        text, _ = self.report("r.md")
        self.assertIn("| R-SM-1 | 2 | 4 | 5 | 626.734667 |", text)
        self.assertIn("| | | | | 101.440000 |", text)
        self.assertNotIn("728.174667", text)

    def test_extra_input_fields_and_markup_never_appear(self):
        doc = json.loads(Path(WL[1]).read_text(encoding="utf-8"))
        doc["firehose_buffers"][0]["DeliveryStreamName"] = "<script>alert(1)</script>"
        doc["firehose_buffers"][0]["RoleArn"] = "arn:aws:iam::123456789012:role/secret-role"
        doc["athena_tables"][0]["query_executions"][0]["Query"] = "SELECT secret_column FROM t"
        bad = self.dir / "ops.json"
        bad.write_text(json.dumps(doc), encoding="utf-8")
        html_text, _ = self.report("r.html", [WL[0], str(bad)])
        md_text, _ = self.report("r.md", [WL[0], str(bad)])
        self.assertNotIn("<script>", html_text)
        self.assertIn("&lt;script&gt;", html_text)
        for text in (html_text, md_text):
            for secret in ("123456789012", "secret-role", "secret_column"):
                self.assertNotIn(secret, text)

    def test_html_is_self_contained(self):
        text, _ = self.report("r.html")
        self.assertTrue(text.startswith("<!doctype html>"))
        self.assertIsNone(re.search(r"<script|<link|src=|https?://", text))
        self.assertIn("prefers-color-scheme:dark", text)

    def test_same_input_same_file_and_examples_current(self):
        for name in ("example-report.html", "example-report.md"):
            a, _ = self.report(name)
            b, _ = self.report("again" + Path(name).suffix)
            self.assertEqual(a, b)
            self.assertEqual(a, (HERE / "reports" / name).read_text(encoding="utf-8"), f"regenerate reports/{name}")

    def test_stdout_unchanged_by_report_option(self):
        plain = cli("--workloads", *WL)
        _, with_report = self.report("r.html")
        self.assertEqual(plain.stdout, with_report.stdout)
        self.assertEqual(cli("--json").stdout, cli("--json", "--report", str(self.dir / "base.md")).stdout)

    def test_report_without_workloads(self):
        path = self.dir / "base.md"
        self.assertEqual(cli("--report", str(path)).returncode, 0)
        text = path.read_text(encoding="utf-8")
        self.assertIn("| EC2·EBS 판정 | 1 | 1 | 3 |", text)
        self.assertNotIn("비용 급증 조사 대기열", text)

    def test_bad_extension_rejected(self):
        r = cli("--report", str(self.dir / "r.pdf"))
        self.assertEqual(r.returncode, 2)

    def test_real_data_kind_changes_header_and_report(self):
        doc = json.loads(Path(WL[0]).read_text(encoding="utf-8"))
        doc["data_kind"] = "real"
        real = self.dir / "real.json"
        real.write_text(json.dumps(doc), encoding="utf-8")
        r = cli("--workloads", str(real))
        self.assertIn("워크로드 규칙 | 실제 입력 |", r.stdout)
        self.assertIn("워크로드 규칙 | 가상 입력 |", cli("--workloads", WL[0]).stdout)
        text, _ = self.report("r.md", [str(real)])
        self.assertIn("**혼합 (합성·실제)**", text)
        self.assertIn("real.json: 실제", text)


if __name__ == "__main__":
    unittest.main()
