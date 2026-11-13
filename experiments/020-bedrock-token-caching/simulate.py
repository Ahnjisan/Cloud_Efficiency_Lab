"""Bedrock prompt caching for a multi-call agent: cost before/after and break-even.

Model of one agent run: k model calls. Every call sends the same fixed prefix
(instructions + tool schema, P tokens), the user input, and the conversation
so far (previous outputs + tool observations). Only the fixed prefix is put
behind a cache checkpoint. Runs arrive as a seeded Poisson process during 12
active hours per day; calls inside a run are 5 s apart.

Cache model: an entry is alive if the previous read or write of the prefix was
less than TTL seconds ago (TTL resets on every hit). With probability `miss`
an otherwise eligible call is served by another server and writes instead of
reading. Prefixes under the model's minimum (512 tokens for the Claude 5.5
models used here) are never cached. Rates come from the Seoul price snapshot.
"""
from itertools import product
from pathlib import Path
import json
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "references" / "aws-price-list-apn2-2026-11-13.json"
ACTIVE_S = 12 * 3600
DAY_S = 24 * 3600
DAYS = 14
CALL_GAP_S = 5
MIN_CACHE_TOKENS = 512
USER_TOKENS, OBS_TOKENS, OUT_TOKENS = 500, 500, 300
USAGE = {
    "input": "input_tokens_global_standard",
    "output": "output_tokens_global_standard",
    "write_5m": "cache_write_tokens_global_standard",
    "write_1h": "cache_write_tokens_1h_global_standard",
    "read": "cache_read_tokens_global_standard",
}
POLICIES = {"none": None, "cache_5m": ("write_5m", 300), "cache_1h": ("write_1h", 3600)}


def load_rates(path=SNAPSHOT):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))["offers"]["AmazonBedrockFoundationModels"]["rows"]
    out = {}
    for model in ("Claude Haiku 5.5", "Claude Sonnet 5.5"):
        out[model] = {}
        for key, suffix in USAGE.items():
            (row,) = [r for r in rows if r["model"] == model and r["usagetype"] == f"APN2-MP:APN2_{suffix}-Units"]
            out[model][key] = float(row["usd"]) / 1_000_000
    return out


def required_hit_ratio(rate, write_key):
    """Share of prefix calls that must hit so caching beats no caching."""
    w, r, i = rate[write_key], rate["read"], rate["input"]
    return (w - i) / (w - r)


def dynamic_tokens(k):
    """Non-prefix input tokens over one run and output tokens over one run."""
    dyn = sum(USER_TOKENS + i * (OUT_TOKENS + OBS_TOKENS) for i in range(k))
    return dyn, k * OUT_TOKENS


def run_times(runs_per_day, seed, days=DAYS):
    rng = random.Random(seed)
    times = []
    for day in range(days):
        t = 0.0
        while True:
            t += rng.expovariate(runs_per_day / ACTIVE_S)
            if t >= ACTIVE_S:
                break
            times.append(day * DAY_S + t)
    return times


def cache_events(times, k, ttl, miss, seed):
    """Count prefix writes and reads over all calls."""
    rng = random.Random(seed * 7919 + k)
    last, writes, reads = None, 0, 0
    for start in times:
        for c in range(k):
            t = start + c * CALL_GAP_S
            alive = last is not None and t - last < ttl
            if alive and rng.random() >= miss:
                reads += 1
            else:
                writes += 1
            last = t
    return writes, reads


def evaluate(model, rate, k, prefix, runs_per_day, policy, miss, seeds):
    dyn, out = dynamic_tokens(k)
    per_seed = []
    for seed in seeds:
        times = run_times(runs_per_day, seed)
        n = len(times)
        base = n * (dyn * rate["input"] + out * rate["output"])
        if POLICIES[policy] is None or prefix < MIN_CACHE_TOKENS:
            prefix_cost, hit = n * k * prefix * rate["input"], 0.0
        else:
            write_key, ttl = POLICIES[policy]
            writes, reads = cache_events(times, k, ttl, miss, seed)
            prefix_cost = prefix * (writes * rate[write_key] + reads * rate["read"])
            hit = reads / (writes + reads)
        per_seed.append({"runs": n, "usd_per_run": (base + prefix_cost) / n, "hit_ratio": hit})
    mean = lambda key: sum(s[key] for s in per_seed) / len(per_seed)
    return {"model": model, "calls": k, "prefix": prefix, "runs_per_day": runs_per_day,
            "policy": policy, "miss": miss,
            "usd_per_run": round(mean("usd_per_run"), 9),
            "usd_per_run_range": [round(min(s["usd_per_run"] for s in per_seed), 9),
                                  round(max(s["usd_per_run"] for s in per_seed), 9)],
            "hit_ratio": round(mean("hit_ratio"), 4),
            "usd_per_month_at_rate": round(mean("usd_per_run") * runs_per_day * 30, 4)}


def main():
    rates = load_rates()
    seeds = (1, 2, 3)
    rows = [evaluate(m, rates[m], k, p, r, pol, miss, seeds)
            for m, k, p, r, pol, miss in product(rates, (1, 2, 4, 8), (500, 1000, 3000, 8000),
                                                 (10, 30, 100, 300, 1000, 10000), POLICIES, (0.0, 0.2))]
    key = lambda r: (r["model"], r["calls"], r["prefix"], r["runs_per_day"], r["miss"])
    none = {key(r): r for r in rows if r["policy"] == "none"}
    for r in rows:
        r["saving_vs_none"] = round(1 - r["usd_per_run"] / none[key(r)]["usd_per_run"], 4)

    cached = [r for r in rows if r["policy"] != "none" and r["prefix"] >= MIN_CACHE_TOKENS]
    worse = [r for r in cached if r["saving_vs_none"] < 0]
    h1 = [r for r in cached if r["model"] == "Claude Haiku 5.5" and r["policy"] == "cache_5m"
          and r["calls"] >= 2 and r["miss"] == 0]
    one_call = [r for r in rows if r["calls"] == 1 and r["prefix"] == 3000 and r["miss"] == 0]
    pick = lambda m, pol, rpd: next(r for r in one_call if (r["model"], r["policy"], r["runs_per_day"]) == (m, pol, rpd))
    h3 = {m: {rpd: {"mean_gap_min": round(ACTIVE_S / rpd / 60, 1),
                    "5m": pick(m, "cache_5m", rpd)["saving_vs_none"],
                    "1h": pick(m, "cache_1h", rpd)["saving_vs_none"]}
              for rpd in (10, 30, 100, 300, 1000, 10000)} for m in rates}
    by_key = {(key(r), r["policy"]): r for r in cached}
    pairs = [(r, by_key[(key(r), "cache_5m")]) for r in cached if r["policy"] == "cache_1h"]
    hypotheses = {
        "H1_haiku_5m_cheaper_whenever_k_ge_2": {"result": all(r["saving_vs_none"] > 0 for r in h1),
                                                 "min_saving": min(r["saving_vs_none"] for r in h1)},
        "H2_cache_loses_only_when_k_eq_1": {"result": all(r["calls"] == 1 for r in worse),
                                            "losing_cases": [{k: r[k] for k in ("model", "calls", "prefix", "runs_per_day", "policy", "miss", "saving_vs_none")}
                                                             for r in worse if r["prefix"] == 3000]},
        "H3_1h_beats_5m_only_for_5_to_60_min_gaps": {
            "result": all(5 <= ACTIVE_S / r1["runs_per_day"] / 60 <= 60 for r1, r5 in pairs
                          if r1["saving_vs_none"] > r5["saving_vs_none"] + 0.001),
            "rows_where_1h_wins_by_gt_0.1pt_outside_5_60_min": sum(
                1 for r1, r5 in pairs if r1["saving_vs_none"] > r5["saving_vs_none"] + 0.001
                and not 5 <= ACTIVE_S / r1["runs_per_day"] / 60 <= 60),
            "rows_where_5m_beats_1h_by_gt_0.1pt": sum(
                1 for r1, r5 in pairs if r5["saving_vs_none"] > r1["saving_vs_none"] + 0.001),
            "one_call_prefix3000": h3},
        "P500_below_minimum_never_cached": {"result": all(r["saving_vs_none"] == 0 for r in rows
                                                          if r["prefix"] == 500)},
    }
    analytic = {m: {"5m": round(required_hit_ratio(rates[m], "write_5m"), 4),
                    "1h": round(required_hit_ratio(rates[m], "write_1h"), 4)} for m in rates}
    print(json.dumps({
        "assumptions": {"active_hours": 12, "days": DAYS, "call_gap_s": CALL_GAP_S,
                        "user_tokens": USER_TOKENS, "observation_tokens": OBS_TOKENS,
                        "output_tokens_per_call": OUT_TOKENS, "min_cache_tokens": MIN_CACHE_TOKENS,
                        "seeds": seeds},
        "rates_usd_per_mtok": {m: {k: round(v * 1e6, 4) for k, v in r.items()} for m, r in rates.items()},
        "required_hit_ratio": analytic,
        "hypotheses": hypotheses,
        "rows": rows,
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
