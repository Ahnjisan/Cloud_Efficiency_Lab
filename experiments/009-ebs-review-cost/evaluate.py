"""Replay freshness and evidence completion over the existing labelled cases."""
from collections import Counter
import json
from pathlib import Path
from runpy import run_path

HERE = Path(__file__).resolve().parent
RULES = run_path(str(HERE.parent / "001-ebs-waste-rules/verify_rules.py"))


def evaluate(cases, evidence, max_age):
    initial, final = Counter(), Counter()
    minutes = 0
    for case in cases:
        volume = RULES["Volume"](**case["input"])
        record = evidence.get(volume.id, {})
        age = record.get("age_days")
        if max_age is not None and volume.evidence == "complete" and (age is None or age > max_age):
            volume = volume._replace(evidence="missing")
        decision = RULES["evidence_rule"](volume)

        def bucket(decision):
            label = case["label"]
            return f"hold_{label}" if decision.status == "hold" else RULES["score"](decision, label)

        initial[bucket(decision)] += 1
        if decision.status == "hold":
            minutes += record.get("review_minutes", 10)
            if "update" in record:
                decision = RULES["evidence_rule"](volume._replace(**record["update"]))
        final[bucket(decision)] += 1
    return {
        "initial": dict(initial), "after_review": dict(final),
        "modeled_hold_review_minutes": minutes,
        "immediate_recall": initial["TP"] / sum(case["label"] == "waste" for case in cases),
    }


def main():
    cases = json.loads((HERE.parent / "002-ebs-rule-robustness/cases.json").read_text(encoding="utf-8"))
    evidence = json.loads((HERE / "evidence.json").read_text(encoding="utf-8"))
    assert set(evidence) <= {case["input"]["id"] for case in cases}
    outcomes = {name: evaluate(cases, evidence, age)
                for name, age in (("no_age_limit", None), ("90_days", 90), ("30_days", 30))}
    baseline, moderate, strict = outcomes.values()
    assert baseline["initial"] == {"TN": 3, "hold_unresolved": 2, "FN": 2,
                                   "hold_normal": 1, "hold_waste": 1, "TP": 1, "FP": 1}
    assert moderate["initial"]["hold_waste"] > baseline["initial"]["hold_waste"]
    assert strict["immediate_recall"] < moderate["immediate_recall"]
    assert strict["modeled_hold_review_minutes"] > moderate["modeled_hold_review_minutes"]
    assert all(item["after_review"]["hold_unresolved"] == 2 for item in outcomes.values())
    print(json.dumps(outcomes, indent=2))


if __name__ == "__main__":
    main()
