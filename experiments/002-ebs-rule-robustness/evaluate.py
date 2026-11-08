"""Evaluate the unchanged 001 rules on new synthetic cases."""
import json
from collections import Counter
from pathlib import Path
from runpy import run_path

here = Path(__file__).resolve().parent
baseline = run_path(str(here.parent / "001-ebs-waste-rules/verify_rules.py"))
cases = json.loads((here / "cases.json").read_text(encoding="utf-8"))
ids = [case["input"]["id"] for case in cases]
assert len(ids) == len(set(ids)) and not set(ids).intersection(baseline["EXPECTED"])

def ratio(a, b):
    return a / b if b else None

results = {}
for name, rule in (("A", "connection_rule"), ("B", "evidence_rule")):
    rows = []
    counts = Counter()
    for case in cases:
        assert case["label"] in {"normal", "waste", "unresolved"} and case["basis"]
        decision = baseline[rule](baseline["Volume"](**case["input"]))
        label = case["label"]
        bucket = f"hold_{label}" if decision.status == "hold" else baseline["score"](decision, label)
        counts[bucket] += 1
        rows.append({"id": case["input"]["id"], "label": label, **decision._asdict(), "bucket": bucket})
    expected = {
        "A": Counter(TP=3, FP=4, FN=1, TN=1, unresolved=2),
        "B": Counter(TP=1, FP=1, FN=2, TN=3, hold_waste=1, hold_normal=1, hold_unresolved=2),
    }
    assert counts == expected[name], counts
    holds = sum(row["status"] == "hold" for row in rows)
    results[name] = {
        "rows": rows, "counts": dict(counts),
        "precision": ratio(counts["TP"], counts["TP"] + counts["FP"]),
        "immediate_recall": ratio(counts["TP"], counts["TP"] + counts["FN"] + counts["hold_waste"]),
        "hold_rate": holds / len(rows),
        "queue": sum(row["status"] in ("hold", "alert") for row in rows),
    }

print(json.dumps(results, indent=2))
