"""Experiment 037: structuring cost of one measurement sheet, by stage."""
from decimal import Decimal as D
import itertools

from rates import CSV_BYTES, GB, HOURS_30D, MODELS, PHOTO_BYTES, TEXTRACT, TOKENS, VOLUMES, WORKDAYS, Rates, emit, money

PHOTO_RATIOS = (D("0.3"), D("0.7"), D("1.0"))
BASE = {"textract": "tables", "model": "Claude Haiku 4.5", "tokens": "medium", "photo": D("0.7")}
Q = D("0.0000001")


def per_sheet(r, volume, textract, model, tokens, photo):
    """Average cost of one sheet (photo share `photo`, rest CSV), by stage."""
    v = VOLUMES[volume]
    pages = v["pages_per_photo_sheet"]
    objects = photo * pages + (1 - photo)            # S3 objects per average sheet
    stored_gb = (photo * pages * PHOTO_BYTES + (1 - photo) * CSV_BYTES) / GB
    tin, tout = TOKENS[tokens]
    return {
        "s3": objects * (r.s3_put + r.s3_get) + stored_gb * r.s3_gb_month,
        "sqs": 3 * r.sqs,
        "textract": photo * pages * r.textract[textract],
        "bedrock": r.bedrock_call(model, tin, tout),
    }


def summarize(parts, volume):
    total = sum(parts.values())
    sheets = VOLUMES[volume]["sheets_per_day"] * WORKDAYS
    return {"per_sheet_usd": str(total.quantize(Q)), "per_1000_sheets_usd": money(total * 1000),
            "monthly_usd": money(total * sheets), "sheets_per_month": sheets,
            "stages_usd": {k: str(v.quantize(Q)) for k, v in parts.items()},
            "share": {k: str((v / total).quantize(D("0.0001"))) for k, v in parts.items()},
            "largest": max(parts, key=parts.get)}


def fixed_monthly(r):
    """Idle polling that does not depend on sheet count (30-day month)."""
    worker = HOURS_30D * 3600 / 20          # one worker, 20 s long polling
    keda = HOURS_30D * 3600 / 30            # KEDA GetQueueAttributes every 30 s
    return {"worker_long_polling_requests": int(worker), "keda_queue_checks": int(keda),
            "usd": money((D(worker) + D(keda)) * r.sqs, "0.0001")}


def evaluate():
    r = Rates()
    grid = []
    for t, m, tok, vol, ph in itertools.product(TEXTRACT, MODELS, TOKENS, VOLUMES, PHOTO_RATIOS):
        s = summarize(per_sheet(r, vol, t, m, tok, ph), vol)
        grid.append({"textract": t, "model": m, "tokens": tok, "volume": vol, "photo": str(ph), **s})
    base = {vol: summarize(per_sheet(r, vol, BASE["textract"], BASE["model"], BASE["tokens"], BASE["photo"]), vol) for vol in VOLUMES}
    sonnet = {vol: summarize(per_sheet(r, vol, BASE["textract"], "Claude Sonnet 4.5", BASE["tokens"], BASE["photo"]), vol) for vol in VOLUMES}
    s3sqs = {vol: (D(b["stages_usd"]["s3"]) + D(b["stages_usd"]["sqs"])) / D(b["per_sheet_usd"]) for vol, b in base.items()}
    ratio = {vol: D(sonnet[vol]["per_sheet_usd"]) / D(base[vol]["per_sheet_usd"]) for vol in VOLUMES}
    bedrock_largest = [g for g in grid if g["largest"] == "bedrock"]
    flips = sorted({(g["textract"], g["model"], g["tokens"], g["photo"]) for g in bedrock_largest})
    return {
        "rates": r.as_dict(), "baseline": {k: str(v) for k, v in BASE.items()},
        "baseline_by_volume": base, "sonnet_by_volume": sonnet, "fixed_monthly_polling": fixed_monthly(r),
        "grid": grid,
        "largest_stage_counts": {k: sum(1 for g in grid if g["largest"] == k) for k in ("s3", "sqs", "textract", "bedrock")},
        "bedrock_largest_conditions": [{"textract": a, "model": b, "tokens": c, "photo": d} for a, b, c, d in flips],
        "hypotheses": {
            "H1_s3_sqs_lt_1pct": {"result": all(v < D("0.01") for v in s3sqs.values()),
                                  "share_by_volume": {k: str(v.quantize(D("0.0001"))) for k, v in s3sqs.items()}},
            "H2_textract_gt_bedrock_baseline": {"result": all(D(b["stages_usd"]["textract"]) > D(b["stages_usd"]["bedrock"]) for b in base.values()),
                                                "by_volume": {k: [b["stages_usd"]["textract"], b["stages_usd"]["bedrock"]] for k, b in base.items()}},
            "H3_sonnet_ge_3x": {"result": all(v >= 3 for v in ratio.values()),
                                "ratio_by_volume": {k: str(v.quantize(D("0.01"))) for k, v in ratio.items()}},
        },
    }


if __name__ == "__main__":
    emit(evaluate())
