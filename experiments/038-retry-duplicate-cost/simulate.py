"""Experiment 038: duplicate and retry processing of measurement sheets (synthetic event simulation).

One message per upload goes through SQS. Each receive starts an attempt (or is skipped by a rule).
An attempt runs OCR on photo pages and calls Bedrock with retries; if it runs past the visibility
timeout the message becomes visible again and another worker receives it while the first attempt
keeps running (and billing). A successful attempt deletes the message.
"""
from decimal import Decimal as D
from pathlib import Path
import heapq
import math
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "037-measurement-sheet-unit-cost"))
from rates import Rates, emit  # noqa: E402

SEEDS = (1, 2, 3)
SHEETS = 5000
TIMEOUTS = (30, 60, 120)
RULES = ("A", "B", "C")
MAX_RECEIVES = 5
LEVELS = {
    "low": {"dup": 0.001, "throttle": 0.01, "bad": 0.01, "manual": 0.05},
    "base": {"dup": 0.01, "throttle": 0.05, "bad": 0.03, "manual": 0.10},
    "high": {"dup": 0.03, "throttle": 0.15, "bad": 0.08, "manual": 0.15},
}
RETRIES = 3
OCR_MEDIAN, OCR_SIGMA = 3.0, 0.5
LLM_MEDIAN, LLM_SIGMA = 10.0, 0.6


def lognorm(rng, median, sigma):
    return rng.lognormvariate(math.log(median), sigma)


def run_job(rng, rule, timeout, p, pages, job, st, c, dup_at=None):
    """Simulate one SQS message (job = 'upload' or 'manual'). Mutates counters c and shared state st."""
    key = "upload" if (rule == "B" or job == "upload") else job   # B: same hash key for both jobs
    attempts = st["attempts"].setdefault(key, [])
    heap = [(0.0 if job == "upload" else st["manual_at"], 0, "first")]
    if job == "upload" and dup_at is not None:
        heapq.heappush(heap, (dup_at, 1, "dup"))
    seq, receives, deleted_at, current = 2, 0, math.inf, None
    while heap:
        t, _, kind = heapq.heappop(heap)
        if kind.startswith("visible"):
            rid = int(kind.split(":")[1])
            if rid != current or deleted_at <= t:
                continue
            last = attempts[-1] if attempts and attempts[-1][3] == rid else None
            kind = "retry_after_fail" if last and not last[2] and last[1] <= t else "redelivery"
        receives += 1
        if receives > MAX_RECEIVES:
            c["dlq"] += 1
            return
        rid = seq; seq += 1
        if kind != "dup":
            current = rid
        if rule in ("B", "C"):
            done = any(s and e <= t for _, e, s, _ in attempts)
            busy = any(b <= t < e for b, e, _, _ in attempts)
            if done or busy:
                c["blocked"][kind if job == "upload" else "manual"] += 1
                if job == "manual" and rule == "B" and done:
                    c["misjudged"] += 1
                if done:
                    deleted_at = min(deleted_at, t)
                elif kind != "dup":
                    heapq.heappush(heap, (t + timeout, seq, f"visible:{rid}")); seq += 1
                continue
        cause = kind if job == "upload" else "manual"
        dur = 1.0
        if pages and not (rule == "C" and st["ocr_stored"]):
            c["ocr_pages"] += pages
            c["ocr_by_cause"][cause] = c["ocr_by_cause"].get(cause, 0) + pages
            dur += sum(lognorm(rng, OCR_MEDIAN, OCR_SIGMA) for _ in range(pages))
            if rule == "C":
                st["ocr_stored"] = True
        ok = False
        for k in range(RETRIES + 1):
            u = rng.random()
            if u < p["throttle"]:
                dur += 2 ** k
                continue
            c["bedrock"] += 1
            c["bedrock_by_cause"][cause] = c["bedrock_by_cause"].get(cause, 0) + 1
            dur += lognorm(rng, LLM_MEDIAN, LLM_SIGMA)
            if u < p["throttle"] + p["bad"]:
                continue
            ok = True
            break
        attempts.append((t, t + dur, ok, rid))
        if ok:
            deleted_at = min(deleted_at, t + dur)
            st["done_at"] = min(st.get("done_at", math.inf), t + dur)
        if kind != "dup":
            heapq.heappush(heap, (t + timeout, seq, f"visible:{rid}")); seq += 1


def simulate(seed, rule, timeout, level):
    rng = random.Random(f"{seed}-{rule}-{timeout}-{level}")       # processing randomness
    sheets_rng = random.Random(f"{seed}-{level}-sheets")         # same sheets for every rule and timeout
    p = LEVELS[level]
    c = {"ocr_pages": 0, "bedrock": 0, "dlq": 0, "misjudged": 0, "blocked": {}, "ocr_by_cause": {}, "bedrock_by_cause": {},
         "ideal_ocr": 0, "ideal_bedrock": 0, "manual_requests": 0}
    c["blocked"] = {k: 0 for k in ("dup", "redelivery", "retry_after_fail", "first", "manual")}
    for _ in range(SHEETS):
        photo = sheets_rng.random() < 0.7
        pages = (2 if sheets_rng.random() < 0.3 else 1) if photo else 0
        manual = sheets_rng.random() < p["manual"]
        dup_at = sheets_rng.uniform(1, 60) if sheets_rng.random() < p["dup"] else None
        st = {"attempts": {}, "ocr_stored": False}
        run_job(rng, rule, timeout, p, pages, "upload", st, c, dup_at)
        c["ideal_ocr"] += pages
        c["ideal_bedrock"] += 1
        if manual and "done_at" in st:
            c["manual_requests"] += 1
            c["ideal_bedrock"] += 1
            st["manual_at"] = st["done_at"] + 3600
            run_job(rng, rule, timeout, p, pages, "manual", st, c)
    return c


def costs(c, r):
    t, b = r.textract["tables"], r.bedrock_call("Claude Haiku 4.5", 3000, 600)
    actual = D(c["ocr_pages"]) * t + D(c["bedrock"]) * b
    ideal = D(c["ideal_ocr"]) * t + D(c["ideal_bedrock"]) * b
    return actual / SHEETS, ideal / SHEETS


def evaluate():
    r = Rates()
    rows = {}
    for level in LEVELS:
        for timeout in TIMEOUTS:
            for rule in RULES:
                per_seed = []
                for seed in SEEDS:
                    c = simulate(seed, rule, timeout, level)
                    cost, ideal = costs(c, r)
                    dup_redel = sum(c["ocr_by_cause"].get(k, 0) for k in ("dup", "redelivery"))
                    per_seed.append({
                        "seed": seed, "ocr_pages_per_sheet": c["ocr_pages"] / SHEETS, "bedrock_per_sheet": c["bedrock"] / SHEETS,
                        "ocr_extra_ratio": c["ocr_pages"] / c["ideal_ocr"] - 1, "cost_per_sheet": cost, "ideal_cost_per_sheet": ideal,
                        "dup_redelivery_ocr_pages": dup_redel, "misjudged": c["misjudged"], "manual_requests": c["manual_requests"],
                        "dlq": c["dlq"], "blocked": c["blocked"], "ocr_by_cause": c["ocr_by_cause"], "bedrock_by_cause": c["bedrock_by_cause"]})
                rows[f"{level}|{timeout}|{rule}"] = per_seed
    out = {}
    for key, ps in rows.items():
        level, timeout, rule = key.split("|")
        a = rows[f"{level}|{timeout}|A"]
        mean = lambda f: sum(f(x) for x in ps) / len(ps)
        rng_ = lambda f: [min(f(x) for x in ps), max(f(x) for x in ps)]
        blocked_ratio = None
        a_dr = sum(x["dup_redelivery_ocr_pages"] for x in a)
        if rule != "A" and a_dr:
            blocked_ratio = 1 - sum(x["dup_redelivery_ocr_pages"] for x in ps) / a_dr
        a_cost = sum(x["cost_per_sheet"] for x in a) / len(a)
        out[key] = {
            "level": level, "timeout_s": int(timeout), "rule": rule,
            "ocr_pages_per_sheet": round(mean(lambda x: x["ocr_pages_per_sheet"]), 4),
            "ocr_pages_per_sheet_range": [round(v, 4) for v in rng_(lambda x: x["ocr_pages_per_sheet"])],
            "bedrock_per_sheet": round(mean(lambda x: x["bedrock_per_sheet"]), 4),
            "ocr_extra_ratio_vs_ideal": round(mean(lambda x: x["ocr_extra_ratio"]), 4),
            "ocr_extra_ratio_range": [round(v, 4) for v in rng_(lambda x: x["ocr_extra_ratio"])],
            "cost_per_sheet_usd": str((sum(x["cost_per_sheet"] for x in ps) / len(ps)).quantize(D("0.000001"))),
            "ideal_cost_per_sheet_usd": str((sum(x["ideal_cost_per_sheet"] for x in ps) / len(ps)).quantize(D("0.000001"))),
            "cost_vs_A": str((sum(x["cost_per_sheet"] for x in ps) / len(ps) / a_cost).quantize(D("0.0001"))),
            "dup_redelivery_blocked_ratio": None if blocked_ratio is None else round(blocked_ratio, 4),
            "misjudged": sum(x["misjudged"] for x in ps), "manual_requests": sum(x["manual_requests"] for x in ps),
            "misjudged_ratio_of_manual": round(sum(x["misjudged"] for x in ps) / max(1, sum(x["manual_requests"] for x in ps)), 4),
            "dlq": sum(x["dlq"] for x in ps),
            "ocr_by_cause_total": {k: sum(x["ocr_by_cause"].get(k, 0) for x in ps) for k in ("first", "dup", "redelivery", "retry_after_fail", "manual")},
        }
    b = lambda lv, to, ru: out[f"{lv}|{to}|{ru}"]
    h3 = all(b("base", to, "C")["misjudged"] == 0 and D(b("base", to, "C")["cost_vs_A"]) <= D("0.9") for to in TIMEOUTS)
    return {
        "rates": {"textract_tables_per_page": str(r.textract["tables"]), "bedrock_haiku_medium_per_call": str(r.bedrock_call("Claude Haiku 4.5", 3000, 600))},
        "config": {"seeds": SEEDS, "sheets_per_seed": SHEETS, "levels": LEVELS, "retries": RETRIES, "max_receives": MAX_RECEIVES,
                   "ocr_time": [OCR_MEDIAN, OCR_SIGMA], "llm_time": [LLM_MEDIAN, LLM_SIGMA]},
        "results": out,
        "hypotheses": {
            "H1_A_timeout30_extra_ocr_ge_10pct": {"result": b("base", 30, "A")["ocr_extra_ratio_vs_ideal"] >= 0.10,
                                                  "extra": b("base", 30, "A")["ocr_extra_ratio_vs_ideal"]},
            "H2_B_blocks_ge_90pct_dup_redelivery_and_misjudges_all_manual": {
                "result": all((b("base", to, "B")["dup_redelivery_blocked_ratio"] or 0) >= 0.9 and b("base", to, "B")["misjudged_ratio_of_manual"] == 1.0 for to in TIMEOUTS),
                "by_timeout": {to: [b("base", to, "B")["dup_redelivery_blocked_ratio"], b("base", to, "B")["misjudged_ratio_of_manual"]] for to in TIMEOUTS}},
            "H3_C_no_misjudge_and_cost_le_90pct_of_A": {
                "result": h3, "by_timeout": {to: [b("base", to, "C")["misjudged"], b("base", to, "C")["cost_vs_A"]] for to in TIMEOUTS}},
        },
    }


if __name__ == "__main__":
    emit(evaluate())
