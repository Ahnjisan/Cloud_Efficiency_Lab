"""Checks for experiment 040 scoring and the CloudShell runner's OCR text builder (no AWS)."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from run_040 import ocr_text
from score import classify, evaluate, match_item, norm, parse_json, wilson

FIELDS = ["sheet_id", "field_id", "spec_item", "kind", "index", "value", "unit", "handwritten", "faint", "corrected"]


class RulesTest(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(norm(" −0.05 "), "-0.05")
        self.assertEqual(norm("+0.10"), "0.10")
        self.assertIsNone(norm(None))

    def test_classify(self):
        self.assertEqual(classify("42.50", "42.5"), (True, False, None))       # trailing zero: correct, not strict
        self.assertEqual(classify("42.50", "42.50"), (True, True, None))
        self.assertEqual(classify("-0.05", "0.05")[2], "sign")
        self.assertEqual(classify("3.20", "32.0")[2], "decimal")
        self.assertEqual(classify("0.006", "0.06")[2], "decimal")
        self.assertEqual(classify("12.02", "12.07")[2], "other")
        self.assertEqual(classify("1.0", None)[2], "missing")
        self.assertEqual(classify("1.0", "ab")[2], "missing")

    def test_parse_json_with_fence(self):
        self.assertEqual(parse_json('```json\n{"items": []}\n```'), {"items": []})
        self.assertIsNone(parse_json("no json"))

    def test_match_item(self):
        items = [{"spec_item": "외경A"}, {"spec_item": "구멍 간격"}]
        self.assertEqual(match_item("외경 A", items)["spec_item"], "외경A")
        self.assertEqual(match_item("구멍간격", items)["spec_item"], "구멍 간격")
        self.assertIsNone(match_item("두께", items))

    def test_wilson(self):
        lo, hi = wilson(0, 805)
        self.assertEqual(lo, 0.0)
        self.assertLess(hi, 0.005)


class FallbackTest(unittest.TestCase):
    def test_row_order_fallback_only_in_posthoc(self):
        from score import score_response
        ans = [{"field_id": "f1", "spec_item": "깊이", "kind": "nominal", "index": "0", "value": "3.20",
                "handwritten": "True", "faint": "False", "corrected": "False"}]
        parsed = {"items": [{"spec_item": "길이", "nominal": "3.20"}]}
        self.assertEqual(score_response(ans, parsed)[0]["error"], "missing")
        self.assertTrue(score_response(ans, parsed)[0]["label_miss"])
        self.assertTrue(score_response(ans, parsed, fallback_by_order=True)[0]["ok"])

    def test_comma_flag(self):
        from score import score_response
        ans = [{"field_id": "f1", "spec_item": "폭", "kind": "nominal", "index": "0", "value": "18.000",
                "handwritten": "True", "faint": "False", "corrected": "False"}]
        r = score_response(ans, {"items": [{"spec_item": "폭", "nominal": "18,000"}]})[0]
        self.assertEqual((r["error"], r["comma_for_period"]), ("missing", True))


class OcrTextTest(unittest.TestCase):
    def test_table_grid(self):
        blocks = [
            {"Id": "t", "BlockType": "TABLE", "Relationships": [{"Type": "CHILD", "Ids": ["c1", "c2"]}]},
            {"Id": "c1", "BlockType": "CELL", "RowIndex": 1, "ColumnIndex": 1, "Relationships": [{"Type": "CHILD", "Ids": ["w1"]}]},
            {"Id": "c2", "BlockType": "CELL", "RowIndex": 1, "ColumnIndex": 2, "Relationships": [{"Type": "CHILD", "Ids": ["w2"]}]},
            {"Id": "w1", "BlockType": "WORD", "Text": "폭"}, {"Id": "w2", "BlockType": "WORD", "Text": "-0.03"},
            {"Id": "l1", "BlockType": "LINE", "Text": "측정 기록지"},
        ]
        text = ocr_text({"Blocks": blocks})
        self.assertIn("| 폭 | -0.03 |", text)
        self.assertIn("측정 기록지", text)


class EvaluateTest(unittest.TestCase):
    def test_end_to_end_on_fake_run(self):
        with tempfile.TemporaryDirectory() as d:
            raw = Path(d)
            (raw / "sheets").mkdir()
            with (raw / "sheets" / "answers.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS)
                w.writeheader()
                for i, (item, kind, val) in enumerate([("폭", "nominal", "18.000"), ("폭", "tol_minus", "-0.03"), ("폭", "measured", "17.995")]):
                    w.writerow({"sheet_id": "S01", "field_id": f"S01-{i}", "spec_item": item, "kind": kind, "index": 0, "value": val,
                                "unit": "mm", "handwritten": "True", "faint": "False", "corrected": "False"})
            (raw / "out" / "textract").mkdir(parents=True)
            (raw / "out" / "textract" / "S01.json").write_text(json.dumps({"pages": 1, "wall_ms": 1000}), encoding="utf-8")
            responses = {"P1": {"nominal": "18.000", "tol_minus": "0.03", "measured": ["17.995"]},   # one sign error
                         "P2": {"nominal": "18.0", "tol_minus": "-0.03", "measured": ["17.995"]},    # all correct
                         "P3": {"nominal": "18.000", "tol_minus": "-0.03", "measured": ["1.7995"]}}  # one decimal error
            for ap, item in responses.items():
                p = raw / "out" / "haiku" / ap / "r1"
                p.mkdir(parents=True)
                body = json.dumps({"items": [{"spec_item": "폭", **item}]}, ensure_ascii=False)
                (p / "S01.json").write_text(json.dumps({"usd_estimate": 0.004 if ap != "P1" else 0.003, "wall_ms": 2000,
                                                        "response": {"output": {"message": {"content": [{"text": body}]}}, "usage": {}}},
                                                       ensure_ascii=False), encoding="utf-8")
            r = evaluate(raw)["results"]
            self.assertEqual(r["haiku|P1"]["errors"]["sign"], 1)
            self.assertEqual(r["haiku|P2"]["accuracy"], 1.0)
            self.assertEqual(r["haiku|P3"]["errors"]["decimal"], 1)
            self.assertEqual(r["haiku|P1"]["usd_per_sheet"], "0.018000")   # 0.003 + Textract 0.015
            self.assertEqual(r["haiku|P2"]["usd_per_sheet"], "0.004000")


class ReproduceTest(unittest.TestCase):
    RAW = Path.home() / "Documents" / "cloud-efficiency-raw" / "040"

    @unittest.skipUnless((RAW / "out").exists(), "raw responses are kept outside the repository")
    def test_result_json_is_reproducible_from_raw(self):
        here = Path(__file__).resolve().parent
        self.assertEqual(json.loads(json.dumps(evaluate(self.RAW), ensure_ascii=False)),
                         json.loads((here / "result.json").read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
