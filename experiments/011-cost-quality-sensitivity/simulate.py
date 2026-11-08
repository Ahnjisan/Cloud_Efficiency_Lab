"""Stress the EC2 decision record across a synthetic scenario grid."""
from collections import Counter
from decimal import Decimal
from itertools import product
import json


def evaluate(helper_hours, peak_hours, overlap_hours, transition, quality):
    minimum = max(0, helper_hours + peak_hours - 720)
    if not minimum <= overlap_hours <= min(helper_hours, peak_hours):
        raise ValueError("impossible overlap")
    common = Decimal("100.40")
    baseline = common + Decimal(".04") * helper_hours
    candidate = common + Decimal(".10") * peak_hours + Decimal(".04") * overlap_hours + transition
    saving = baseline - candidate
    decision = ("hold" if quality == "unknown" else
                "candidate" if quality == "pass" and saving > 0 else "keep")
    return {"baseline": str(baseline), "candidate_first_month": str(candidate),
            "first_month_saving": str(saving), "decision": decision}


def main():
    grid = []
    for h, p, transition, quality in product(
        (0, 360, 720), (0, 120, 205, 206), map(Decimal, ("0", "5", "15")), ("pass", "fail", "unknown")
    ):
        for overlap in sorted({max(0, h + p - 720), min(h, p)}):
            grid.append({"helper_hours": h, "peak_hours": p, "overlap_hours": overlap,
                         "transition": str(transition), "quality": quality,
                         **evaluate(h, p, overlap, transition, quality)})
    assert evaluate(720, 120, 120, Decimal(0), "pass")["first_month_saving"] == "12.00"
    assert evaluate(360, 120, 0, Decimal(0), "pass")["decision"] == "candidate"
    assert evaluate(360, 120, 120, Decimal(0), "pass")["decision"] == "keep"
    assert evaluate(720, 205, 205, Decimal(0), "pass")["decision"] == "candidate"
    assert evaluate(720, 206, 206, Decimal(0), "pass")["decision"] == "keep"
    assert evaluate(720, 120, 120, Decimal(12), "pass")["decision"] == "keep"
    assert evaluate(720, 120, 120, Decimal(0), "unknown")["decision"] == "hold"
    assert evaluate(720, 120, 120, Decimal(0), "fail")["decision"] == "keep"
    print(json.dumps({"counts": dict(Counter(row["decision"] for row in grid)), "scenarios": grid}, indent=2))


if __name__ == "__main__":
    main()
