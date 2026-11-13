"""Simple daily cost spike rules on synthetic series: false alarms, misses, delay.

Each synthetic series has 56 warm-up days and 365 evaluation days: a base
level with slow trend, a weekend dip, multiplicative noise, injected 1-3 day
spikes and gradual ramps (level shifts). Rule parameters are chosen on tuning
seeds only and then evaluated on separate test seeds.
"""
from itertools import product
import json
import random
import statistics
import sys

WARMUP, DAYS = 56, 365
TUNE_SEEDS = tuple(range(1, 21))
TEST_SEEDS = tuple(range(101, 121))
FP_BUDGET_PER_30 = 1.0  # pre-registered selection constraint


def make_series(seed, spike_range=(0.5, 3.0)):
    rng = random.Random(seed)
    n = WARMUP + DAYS
    base = rng.uniform(10, 50)
    weekend = rng.uniform(0.6, 0.8)
    sigma = rng.uniform(0.05, 0.12)
    trend = rng.uniform(0.0, 0.15) / 365
    expected = [base * (1 + trend * d) * (weekend if d % 7 in (5, 6) else 1.0) for d in range(n)]
    shift = [1.0] * n
    labels = [None] * n
    events = []
    for _ in range(rng.randint(1, 2)):  # gradual ramps in the evaluation period
        start = rng.randrange(WARMUP + 30, n - 60)
        length, height = rng.randint(21, 42), rng.uniform(0.4, 0.8)
        if any(labels[d] for d in range(start, start + length)):
            continue
        for d in range(start, n):
            shift[d] *= 1 + height * min(1.0, (d - start + 1) / length)
        for d in range(start, start + length):
            labels[d] = ("growth", len(events))
        events.append({"type": "growth", "start": start, "length": length, "height": round(height, 3)})
    for _ in range(rng.randint(4, 8)):
        start, length = rng.randrange(WARMUP, n - 3), rng.randint(1, 3)
        if any(labels[d] for d in range(start - 3, min(n, start + length + 3))):
            continue
        mag = rng.uniform(*spike_range)
        for d in range(start, start + length):
            labels[d] = ("spike", len(events))
        events.append({"type": "spike", "start": start, "length": length, "magnitude": round(mag, 3)})
    cost = []
    for d in range(n):
        x = expected[d] * shift[d] * rng.lognormvariate(0, sigma)
        if labels[d] and labels[d][0] == "spike":
            x *= 1 + events[labels[d][1]]["magnitude"]
        cost.append(round(x, 2))
    return {"seed": seed, "cost": cost, "labels": labels, "events": events}


def history(cost, d, excluded, window, same_weekday=False):
    out, j = [], d - 1
    while j >= 0 and len(out) < window:
        if j not in excluded and (not same_weekday or (d - j) % 7 == 0):
            out.append(cost[j])
        j -= 1
    return out


def alert(rule, param, cost, d, excluded):
    x = cost[d]
    if rule == "R1_mean_sd14":
        h = history(cost, d, excluded, 14)
        return len(h) >= 7 and x > statistics.fmean(h) + param * statistics.pstdev(h)
    if rule == "R2_median_mad28":
        h = history(cost, d, excluded, 28)
        if len(h) < 14:
            return False
        m = statistics.median(h)
        mad = statistics.median(abs(v - m) for v in h)
        return x > m + param * 1.4826 * mad and x - m > 0.1 * m
    if rule == "R3_weekday_median4":
        h = history(cost, d, excluded, 4, same_weekday=True)
        if len(h) < 3:
            return False
        m = statistics.median(h)
        return x > m * (1 + param) and x - m > 0.1 * m
    raise ValueError(rule)


RULES = {
    "R1_mean_sd14": (2.0, 2.5, 3.0, 3.5, 4.0),
    "R2_median_mad28": (3.0, 4.0, 5.0, 6.0, 8.0),
    "R3_weekday_median4": (0.2, 0.3, 0.5, 0.75, 1.0),
}


def score(series, rule, param, exclude_alerts):
    cost, labels = series["cost"], series["labels"]
    excluded, alerts = set(), []
    for d in range(WARMUP, len(cost)):
        if alert(rule, param, cost, d, excluded):
            alerts.append(d)
            if exclude_alerts:
                excluded.add(d)
    alert_set = set(alerts)
    normal_days = [d for d in range(WARMUP, len(cost)) if labels[d] is None]
    fp_days = [d for d in normal_days if d in alert_set]
    res = {"fp": len(fp_days), "normal_days": len(normal_days),
           "fp_weekday": [sum(1 for d in fp_days if d % 7 == w) for w in range(7)],
           "spike": [0, 0], "growth": [0, 0], "delays": []}
    for i, e in enumerate(series["events"]):
        days = range(e["start"], e["start"] + e["length"])
        hit = [d for d in days if d in alert_set]
        res[e["type"]][1] += 1
        if hit:
            res[e["type"]][0] += 1
            if e["type"] == "spike":
                res["delays"].append(hit[0] - e["start"])
    return res


def aggregate(results):
    fp = sum(r["fp"] for r in results)
    normal = sum(r["normal_days"] for r in results)
    sp = [sum(r["spike"][i] for r in results) for i in (0, 1)]
    gr = [sum(r["growth"][i] for r in results) for i in (0, 1)]
    delays = [x for r in results for x in r["delays"]]
    weekday = [sum(r["fp_weekday"][w] for r in results) for w in range(7)]
    return {
        "spike_recall": round(sp[0] / sp[1], 4), "spike_events": sp[1],
        "growth_recall": round(gr[0] / gr[1], 4), "growth_events": gr[1],
        "fp_per_30_normal_days": round(fp / normal * 30, 4), "false_alarm_rate": round(fp / normal, 5),
        "fp_by_day_index_mod7": weekday,
        "mean_delay_days": round(statistics.fmean(delays), 3) if delays else None,
        "delay_histogram": {k: delays.count(k) for k in sorted(set(delays))},
    }


def evaluate(seeds, rule, param, exclude_alerts, cache):
    return aggregate([score(cache[s], rule, param, exclude_alerts) for s in seeds])


def main():
    cache = {s: make_series(s) for s in TUNE_SEEDS + TEST_SEEDS}
    curves, chosen = [], {}
    for rule, excl in product(RULES, (False, True)):
        tuned = []
        for p in RULES[rule]:
            tune = evaluate(TUNE_SEEDS, rule, p, excl, cache)
            test = evaluate(TEST_SEEDS, rule, p, excl, cache)
            curves.append({"rule": rule, "param": p, "exclude_alerts": excl, "tune": tune, "test": test})
            tuned.append((p, tune, test))
        feasible = [t for t in tuned if t[1]["fp_per_30_normal_days"] <= FP_BUDGET_PER_30]
        pool = feasible or [min(tuned, key=lambda t: t[1]["fp_per_30_normal_days"])]
        p, tune, test = max(pool, key=lambda t: (t[1]["spike_recall"], -t[1]["fp_per_30_normal_days"]))
        chosen[f"{rule}|exclude={excl}"] = {"param": p, "feasible_on_tune": bool(feasible),
                                            "tune": tune, "test": test}
    r1, r3 = chosen["R1_mean_sd14|exclude=True"]["test"], chosen["R3_weekday_median4|exclude=True"]["test"]
    r1n, r3n = chosen["R1_mean_sd14|exclude=False"]["test"], chosen["R3_weekday_median4|exclude=False"]["test"]
    hypotheses = {
        "H1_R3_fewer_false_alarms_than_R1_at_similar_recall": {
            "criterion": "R3 test FP/30 <= R1 and R3 spike recall >= R1 recall - 0.05 (both exclusion settings)",
            "result": all(b["fp_per_30_normal_days"] <= a["fp_per_30_normal_days"]
                          and b["spike_recall"] >= a["spike_recall"] - 0.05 for a, b in ((r1, r3), (r1n, r3n))),
            "R1": {k: r1[k] for k in ("spike_recall", "fp_per_30_normal_days")},
            "R3": {k: r3[k] for k in ("spike_recall", "fp_per_30_normal_days")},
        },
        "H2_all_rules_growth_recall_below_20pct": {
            "result": all(c["test"]["growth_recall"] < 0.20 for c in chosen.values()),
            "growth_recall": {k: c["test"]["growth_recall"] for k, c in chosen.items()},
        },
    }
    sample = make_series(TEST_SEEDS[0])
    print(json.dumps({
        "design": {"warmup_days": WARMUP, "eval_days": DAYS, "tune_seeds": [TUNE_SEEDS[0], TUNE_SEEDS[-1]],
                   "test_seeds": [TEST_SEEDS[0], TEST_SEEDS[-1]], "fp_budget_per_30_normal_days": FP_BUDGET_PER_30,
                   "selection": "max tuning spike recall subject to FP budget; ties -> fewer FP",
                   "weekend_day_index_mod7": [5, 6]},
        "hypotheses": hypotheses, "chosen": chosen, "curves": curves,
        "sample_test_series_events": sample["events"],
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
