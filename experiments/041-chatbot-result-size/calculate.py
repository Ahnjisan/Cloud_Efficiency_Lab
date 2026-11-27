"""Experiment 041: how much of a SQL result the chatbot passes to the LLM, and what it costs."""
from decimal import Decimal as D
from pathlib import Path
import csv
import io
import json
import math
import random
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "037-measurement-sheet-unit-cost"))
from rates import Rates, emit, money  # noqa: E402

SEED = 41
ROWS = (10, 50, 200, 1000)
CALLS = (3, 4, 6)
QUESTIONS_PER_DAY = (50, 200, 1000)
WORKDAYS = 22
CONTEXT_LIMIT = 200_000
PREFIX, QUESTION, FIND_RESULT, OUT = 2000, 100, 200, 300
MIN_CACHE = {"Claude Haiku 4.5": 4096, "Claude Sonnet 4.5": None}  # Sonnet 4.5 minimum not confirmed -> no caching computed
RATIOS = {"low": (4.0, 0.7), "base": (3.5, 1.0), "high": (2.5, 1.5)}   # (ASCII chars per token, tokens per non-ASCII char)
ALL_COLS = ["record_id", "company_code", "drawing_no", "spec_item", "nominal", "tol_plus", "tol_minus", "measured",
            "unit", "judgment", "inspector_id", "measured_at"]
NEED_COLS = ["spec_item", "nominal", "measured", "judgment", "measured_at"]
ITEMS = ["외경 A", "외경 B", "내경 A", "길이", "폭", "두께", "평면도", "직각도", "깊이", "구멍 간격"]


def synth_rows(n, seed=SEED):
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        item = ITEMS[i % len(ITEMS)]
        nominal = round(10 + (i % len(ITEMS)) * 2.5, 3)
        tol = 0.02 if i % 3 else 0.05
        measured = round(nominal + rng.gauss(0, tol / 2), 3)
        rows.append({"record_id": 100000 + i, "company_code": f"C{rng.randint(1, 40):03d}", "drawing_no": f"DWG-2026-{rng.randint(1, 300):04d}",
                     "spec_item": item, "nominal": f"{nominal:.3f}", "tol_plus": f"{tol:.3f}", "tol_minus": f"{-tol:.3f}",
                     "measured": f"{measured:.3f}", "unit": "mm", "judgment": "합격" if abs(measured - nominal) <= tol else "불합격",
                     "inspector_id": f"U{rng.randint(1, 60):04d}", "measured_at": f"2026-11-{1 + i % 26:02d}T{8 + i % 10:02d}:{i % 60:02d}:00"})
    return rows


def aggregate(rows):
    out = []
    for item in ITEMS:
        vals = [float(r["measured"]) for r in rows if r["spec_item"] == item]
        if not vals:
            continue
        out.append({"spec_item": item, "count": len(vals), "fail": sum(1 for r in rows if r["spec_item"] == item and r["judgment"] == "불합격"),
                    "mean": f"{statistics.fmean(vals):.4f}", "min": f"{min(vals):.3f}", "max": f"{max(vals):.3f}",
                    "stdev": f"{statistics.pstdev(vals):.4f}"})
    return out


def serialize(rows, cols, fmt):
    data = [{c: r[c] for c in cols} for r in rows]
    if fmt == "json":
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    w.writerows(data)
    return buf.getvalue()


def tokens(text, ratio):
    ascii_chars = sum(1 for ch in text if ord(ch) < 128)
    other = len(text) - ascii_chars
    per_ascii, per_other = RATIOS[ratio]
    return math.ceil(ascii_chars / per_ascii + other * per_other)


def call_inputs(result_tokens, k):
    """Input tokens of each of k calls; the SQL result enters after call 2 and is re-sent in later calls."""
    hist = [FIND_RESULT + OUT, result_tokens + OUT] + [OUT] * max(0, k - 2)
    return [PREFIX + QUESTION + sum(hist[:i]) for i in range(k)]


def question_cost(r, model, result_tokens, k, cache):
    rate = r.model[model]
    ins = call_inputs(result_tokens, k)
    cost, written = D(0), 0
    mn = MIN_CACHE[model]
    for total_in in ins:
        if cache and mn is not None:
            read = written if written and written <= total_in else 0
            write = (total_in - read) if total_in >= mn else 0
            if write:
                written = total_in
            cost += D(read) * rate["cache_read"] + D(write) * rate["cache_write"] + D(total_in - read - write) * rate["in"]
        else:
            cost += D(total_in) * rate["in"]
        cost += D(OUT) * rate["out"]
    return cost, max(ins), sum(ins)


def evaluate():
    r = Rates()
    payload = {}
    for n in ROWS:
        rows = synth_rows(n)
        for shape in ("raw", "aggregated"):
            data = rows if shape == "raw" else aggregate(rows)
            for cols_name in ("all", "needed"):
                if shape == "aggregated" and cols_name == "needed":
                    continue
                cols = (ALL_COLS if cols_name == "all" else NEED_COLS) if shape == "raw" else list(data[0].keys())
                for fmt in ("json", "csv"):
                    text = serialize(data, cols, fmt)
                    payload[f"{n}|{shape}|{cols_name}|{fmt}"] = {"rows": n, "shape": shape, "cols": cols_name, "format": fmt,
                                                                 "chars": len(text), "tokens": {k: tokens(text, k) for k in RATIOS}}
    grid = []
    for key, p in payload.items():
        for model in ("Claude Haiku 4.5", "Claude Sonnet 4.5"):
            for k in CALLS:
                for cache in (False, True):
                    if cache and MIN_CACHE[model] is None:
                        continue
                    for ratio in RATIOS:
                        c, mx, tot = question_cost(r, model, p["tokens"][ratio], k, cache)
                        grid.append({**{x: p[x] for x in ("rows", "shape", "cols", "format")}, "model": model, "calls": k, "cache": cache,
                                     "ratio": ratio, "result_tokens": p["tokens"][ratio], "max_call_input": mx, "total_input": tot,
                                     "over_context_limit": mx > CONTEXT_LIMIT, "usd_per_question": str(c.quantize(D("0.000001"))),
                                     "monthly_usd": {str(q): money(c * q * WORKDAYS) for q in QUESTIONS_PER_DAY}})
    pick = lambda **kw: next(g for g in grid if all(g[a] == b for a, b in kw.items()))
    base = dict(model="Claude Haiku 4.5", calls=4, cache=False, ratio="base")
    raw = pick(rows=1000, shape="raw", cols="all", format="json", **base)
    agg = pick(rows=1000, shape="aggregated", cols="all", format="json", **base)
    h2 = {n: payload[f"{n}|raw|all|json"]["tokens"]["base"] / payload[f"{n}|raw|all|csv"]["tokens"]["base"] for n in ROWS}
    limit = sorted({(g["rows"], g["shape"], g["cols"], g["format"], g["ratio"]) for g in grid if g["over_context_limit"]})
    return {
        "assumptions": {"prefix": PREFIX, "question": QUESTION, "find_result": FIND_RESULT, "output_per_call": OUT, "ratios": RATIOS,
                        "context_limit": CONTEXT_LIMIT, "workdays": WORKDAYS, "seed": SEED, "min_cache": MIN_CACHE},
        "payload": payload, "grid": grid,
        "over_context_limit_conditions": [{"rows": a, "shape": b, "cols": c, "format": d, "ratio": e} for a, b, c, d, e in limit],
        "hypotheses": {
            "H1_raw_1000_json_ge_10x_aggregated": {"result": D(raw["usd_per_question"]) >= 10 * D(agg["usd_per_question"]),
                                                   "raw_usd": raw["usd_per_question"], "aggregated_usd": agg["usd_per_question"],
                                                   "ratio": str((D(raw["usd_per_question"]) / D(agg["usd_per_question"])).quantize(D("0.01")))},
            "H2_json_ge_1_3x_csv": {"result": all(v >= 1.3 for v in h2.values()), "ratio_by_rows": {k: round(v, 3) for k, v in h2.items()}},
            "H3_raw_1000_json_over_200k": {"result": raw["over_context_limit"], "max_call_input": raw["max_call_input"]},
        },
    }


if __name__ == "__main__":
    emit(evaluate())
