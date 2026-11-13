"""SageMaker GPU training: always-on notebook vs schedule vs training jobs.

Deterministic monthly calculation (720 h, 22 working days of 8 h) with the
Seoul price snapshot. Residual cost = what keeps billing after all compute
stops (notebook ML storage and S3 artifacts).
"""
from itertools import product
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "references" / "aws-price-list-apn2-2026-11-13.json"
MONTH_H = 720
WORK_H = 22 * 8


def load_rates(path=SNAPSHOT):
    offers = json.loads(Path(path).read_text(encoding="utf-8"))["offers"]
    sm = {r["usagetype"]: float(r["usd"]) for r in offers["AmazonSageMaker"]["rows"]}
    s3 = next(float(r["usd"]) for r in offers["AmazonS3"]["rows"]
              if r["usagetype"] == "APN2-TimedStorage-ByteHrs" and float(r["begin"]) == 0)
    return {
        "nb_cpu": sm["APN2-Notebk:ml.t3.medium"], "nb_g4dn": sm["APN2-Notebk:ml.g4dn.xlarge"],
        "train_g4dn": sm["APN2-Train:ml.g4dn.xlarge"], "train_g5": sm["APN2-Train:ml.g5.xlarge"],
        "nb_storage": sm["APN2-Notebk:VolumeUsage.gp2"], "train_storage": sm["APN2-Train:VolumeUsage.gp2"],
        "s3": s3,
    }


def month(scenario, train_h, nb_gb, artifact_gb, train_gb, gpu, rates):
    if not 0 <= train_h <= WORK_H:
        raise ValueError("training hours must fit in working hours")
    storage = nb_gb * rates["nb_storage"] + artifact_gb * rates["s3"]
    if scenario == "gpu_notebook_always_on":
        compute = MONTH_H * rates["nb_g4dn"]
    elif scenario == "gpu_notebook_scheduled":
        compute = WORK_H * rates["nb_g4dn"]
    elif scenario == "cpu_notebook_scheduled_plus_training_jobs":
        compute = WORK_H * rates["nb_cpu"] + train_h * rates[f"train_{gpu}"]
        storage += train_gb * rates["train_storage"] * train_h / MONTH_H
    else:
        raise ValueError(scenario)
    return {"scenario": scenario, "train_h": train_h, "gpu": gpu, "notebook_gb": nb_gb,
            "compute_usd": round(compute, 4), "storage_usd": round(storage, 4),
            "total_usd": round(compute + storage, 4),
            "residual_after_stop_usd": round(nb_gb * rates["nb_storage"] + artifact_gb * rates["s3"], 4),
            "gpu_busy_share_of_billed_gpu_hours": round(
                train_h / (MONTH_H if scenario == "gpu_notebook_always_on" else WORK_H), 4)
            if scenario != "cpu_notebook_scheduled_plus_training_jobs" else 1.0}


def main():
    rates = load_rates()
    rows = [month(s, t, nb, 20, 50, gpu, rates)
            for s, t, nb, gpu in product(("gpu_notebook_always_on", "gpu_notebook_scheduled",
                                          "cpu_notebook_scheduled_plus_training_jobs"),
                                         (4, 16, 40, 80, 160), (20, 50), ("g4dn", "g5"))
            if not (gpu == "g5" and s != "cpu_notebook_scheduled_plus_training_jobs")]
    get = lambda s, t, gpu="g4dn", nb=50: next(r for r in rows if (r["scenario"], r["train_h"], r["gpu"], r["notebook_gb"]) == (s, t, gpu, nb))
    ratio = lambda t: get("gpu_notebook_always_on", t)["total_usd"] / get("cpu_notebook_scheduled_plus_training_jobs", t)["total_usd"]
    break_even = (WORK_H * rates["nb_g4dn"] - WORK_H * rates["nb_cpu"]) / rates["train_g4dn"]
    hypotheses = {
        "H1_always_on_ge_10x_training_jobs_at_16h": {"result": ratio(16) >= 10, "ratio": round(ratio(16), 2),
                                                     "ratio_by_train_h": {t: round(ratio(t), 2) for t in (4, 16, 40, 80, 160)}},
        "H2_residual_after_stop_is_storage_only_and_positive": {
            "result": all(r["residual_after_stop_usd"] > 0 for r in rows),
            "residual_usd": {nb: get("gpu_notebook_always_on", 16, nb=nb)["residual_after_stop_usd"] for nb in (20, 50)}},
    }
    print(json.dumps({"rates": rates, "month_hours": MONTH_H, "work_hours": WORK_H,
                      "assumptions": {"artifact_gb_s3": 20, "training_volume_gb": 50},
                      "break_even_train_h_scheduled_gpu_notebook_vs_jobs": round(break_even, 1),
                      "hypotheses": hypotheses, "rows": rows}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
