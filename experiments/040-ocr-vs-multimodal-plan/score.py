"""Score experiment 040 responses against the answer key and aggregate accuracy and cost.

Usage: py -3 -B score.py <raw_dir>   (raw_dir holds sheets/answers.csv and out/ from CloudShell)
Prints result JSON. Scoring rules are fixed before the run (README, 실행 전 결정).
"""
from decimal import Decimal, InvalidOperation
from pathlib import Path
import csv
import difflib
import json
import math
import re
import sys

APPROACHES = ("P1", "P2", "P3")
MODELS = ("haiku", "sonnet")
TEXTRACT_PAGE = Decimal("0.015")


def norm(v):
    """Normalize a value string: spaces, unicode minus/dash, leading '+'. None stays None."""
    if v is None:
        return None
    s = str(v).strip().replace(" ", "").replace("−", "-").replace("–", "-").replace("—", "-").replace("＋", "+").replace("，", ".")
    s = s.lstrip("+") if s.startswith("+") else s
    return s or None


def to_dec(s):
    try:
        return Decimal(s)
    except (InvalidOperation, TypeError):
        return None


def classify(truth, got):
    """Return (correct, strict_correct, error_class)."""
    t, g = norm(truth), norm(got)
    if g is None:
        return False, False, "missing"
    td, gd = to_dec(t), to_dec(g)
    if gd is None:
        return False, False, "missing"
    if td == gd:
        return True, t == g, None
    if abs(td) == abs(gd):
        return False, False, "sign"
    digits = lambda s: s.lstrip("-").replace(".", "").lstrip("0")
    if digits(t) == digits(g):
        return False, False, "decimal"
    return False, False, "other"


def parse_json(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def key(s):
    return re.sub(r"\s+", "", s or "")


def match_item(name, items):
    by = {key(it.get("spec_item")): it for it in items if isinstance(it, dict)}
    if key(name) in by:
        return by[key(name)]
    best = difflib.get_close_matches(key(name), list(by), n=1, cutoff=0.6)
    return by[best[0]] if best else None


def field_value(item, kind, index):
    if item is None:
        return None
    if kind == "measured":
        vals = item.get("measured") or []
        if not isinstance(vals, list):
            vals = [vals]
        return vals[index] if index < len(vals) else None
    return item.get(kind)


def wilson(errors, n, z=1.96):
    if n == 0:
        return [None, None]
    p = errors / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, c - h), 5), round(min(1.0, c + h), 5)]


def score_response(answers, parsed, fallback_by_order=False):
    """fallback_by_order: post-hoc analysis only (not used for hypotheses) — when the item name does not
    match, take the response item at the same row position, to separate label misreads from number misreads."""
    items = (parsed or {}).get("items") or []
    order = list(dict.fromkeys(a["spec_item"] for a in answers))
    rows = []
    for a in answers:
        item = match_item(a["spec_item"], items)
        label_miss = item is None
        if label_miss and fallback_by_order:
            i = order.index(a["spec_item"])
            item = items[i] if i < len(items) and isinstance(items[i], dict) else None
        got = field_value(item, a["kind"], int(a["index"]))
        ok, strict, err = classify(a["value"], got)
        comma = isinstance(got, str) and re.fullmatch(r"[+\-−]?\d+,\d+", got.strip()) is not None
        rows.append({"field_id": a["field_id"], "handwritten": a["handwritten"] == "True", "faint": a["faint"] == "True",
                     "corrected": a["corrected"] == "True", "kind": a["kind"], "ok": ok, "strict": strict, "error": err,
                     "label_miss": label_miss, "comma_for_period": comma})
    return rows


def aggregate(rows):
    hw = [r for r in rows if r["handwritten"]]
    n = len(hw)
    errs = [r for r in hw if not r["ok"]]
    out = {"fields": n, "accuracy": round(1 - len(errs) / n, 5) if n else None,
           "strict_accuracy": round(sum(r["strict"] for r in hw) / n, 5) if n else None,
           "error_rate_wilson95": wilson(len(errs), n),
           "errors": {c: sum(1 for r in errs if r["error"] == c) for c in ("missing", "sign", "decimal", "other")},
           "printed_accuracy": None}
    pr = [r for r in rows if not r["handwritten"]]
    if pr:
        out["printed_accuracy"] = round(sum(r["ok"] for r in pr) / len(pr), 5)
    hard = [r for r in hw if r["faint"] or r["corrected"]]
    out["hard_fields_correct"] = f"{sum(r['ok'] for r in hard)}/{len(hard)}"
    neg = [r for r in hw if r["kind"] in ("tol_minus", "deviation")]
    out["sign_error_rate_on_signed_fields"] = round(sum(r["error"] == "sign" for r in neg) / len(neg), 5) if neg else None
    out["fields_with_label_misread"] = sum(r["label_miss"] for r in hw)
    out["comma_for_period_in_missing"] = sum(r["comma_for_period"] for r in hw)
    return out


def evaluate(raw):
    raw = Path(raw)
    answers = list(csv.DictReader((raw / "sheets" / "answers.csv").open(encoding="utf-8")))
    by_sheet = {}
    for a in answers:
        by_sheet.setdefault(a["sheet_id"], []).append(a)
    out_dir = raw / "out"
    textract = {}
    for f in sorted((out_dir / "textract").glob("S*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        textract[f.stem] = {"pages": d["pages"], "wall_ms": d["wall_ms"]}
    results, per_rep = {}, {}
    for model in MODELS:
        for ap in APPROACHES:
            rows_all, rows_post, costs, lat, parse_fail, calls, errors = [], [], [], [], 0, 0, 0
            for rep_dir in sorted((out_dir / model / ap).glob("r*")) if (out_dir / model / ap).exists() else []:
                rep_rows = []
                for sid, ans in sorted(by_sheet.items()):
                    f = rep_dir / f"{sid}.json"
                    if not f.exists():
                        if (rep_dir / f"{sid}.error.txt").exists():
                            errors += 1
                        continue
                    d = json.loads(f.read_text(encoding="utf-8"))
                    calls += 1
                    text = "".join(c.get("text", "") for c in d["response"]["output"]["message"]["content"])
                    parsed = parse_json(text)
                    parse_fail += parsed is None
                    rows = score_response(ans, parsed)
                    rep_rows += rows
                    rows_post += score_response(ans, parsed, fallback_by_order=True)
                    u = d["response"].get("usage", {})
                    usd = Decimal(str(d["usd_estimate"]))
                    if ap in ("P1", "P3") and sid in textract:
                        usd += TEXTRACT_PAGE * textract[sid]["pages"]
                    costs.append(usd)
                    lat.append(d["wall_ms"] + (textract[sid]["wall_ms"] if ap in ("P1", "P3") and sid in textract else 0))
                per_rep[f"{model}|{ap}|{rep_dir.name}"] = aggregate(rep_rows) if rep_rows else None
                rows_all += rep_rows
            if not calls:
                continue
            lat.sort()
            agg = aggregate(rows_all)
            post = aggregate(rows_post)
            agg["posthoc_row_order_fallback"] = {"accuracy": post["accuracy"], "error_rate_wilson95": post["error_rate_wilson95"],
                                                 "errors": post["errors"], "note": "post-hoc, not used for hypotheses"}
            agg.update({"calls": calls, "call_errors": errors, "json_parse_failures": parse_fail,
                        "usd_per_sheet": str((sum(costs) / len(costs)).quantize(Decimal("0.000001"))),
                        "latency_ms_p50": lat[len(lat) // 2], "latency_ms_p95": lat[min(len(lat) - 1, int(len(lat) * 0.95))]})
            results[f"{model}|{ap}"] = agg
    g = lambda m, ap, k: results.get(f"{m}|{ap}", {}).get(k)
    hyp = {}
    for m in MODELS:
        if all(f"{m}|{ap}" in results for ap in APPROACHES):
            dec_sign = {ap: (results[f"{m}|{ap}"]["errors"]["sign"] + results[f"{m}|{ap}"]["errors"]["decimal"]) for ap in APPROACHES}
            hyp[m] = {
                "H1_P2_not_worse_than_P1_by_1pp": {"result": g(m, "P2", "accuracy") >= g(m, "P1", "accuracy") - 0.01,
                                                    "P1": g(m, "P1", "accuracy"), "P2": g(m, "P2", "accuracy")},
                "H2_P2_cost_le_half_P1": {"result": Decimal(g(m, "P2", "usd_per_sheet")) <= Decimal(g(m, "P1", "usd_per_sheet")) / 2,
                                          "P1": g(m, "P1", "usd_per_sheet"), "P2": g(m, "P2", "usd_per_sheet")},
                "H3_P3_lowest_sign_decimal_errors": {"result": dec_sign["P3"] < min(dec_sign["P1"], dec_sign["P2"]), "counts": dec_sign},
            }
    return {"answers": {"fields": len(answers), "handwritten": sum(a["handwritten"] == "True" for a in answers), "sheets": len(by_sheet)},
            "textract_pages": sum(t["pages"] for t in textract.values()), "results": results, "per_rep": per_rep, "hypotheses": hyp}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(evaluate(sys.argv[1]), indent=1, ensure_ascii=False))
