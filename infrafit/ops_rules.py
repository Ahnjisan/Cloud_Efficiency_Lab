"""Read-only operational rules: Firehose buffers, Athena tables, SageMaker idle, cost spikes.

Rules R-FH-2, R-ATH-1, R-ATH-2, R-SM-1 (decisions) and R-COST-1 (an
investigation queue, not a decision) from experiments/infrafit-pipeline-ai-rules.md.
Input field names follow the AWS APIs and metrics they come from (BufferingHints,
CloudWatch, S3 Inventory, Athena QueryExecution, Glue StorageDescriptor,
SageMaker DescribeNotebookInstance, Cost Explorer GetCostAndUsage). Values a
person has to provide (allowed freshness, always-on requirement, notebook GPU
activity) hold only their own item when missing.
"""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import math
import statistics

from workload_rules import ROOT, decision, is_count, load_json, value

MIB = 1024 * 1024
DAY_S = 86_400
REASONS = {
    "input-invalid": "필수 입력이 없거나 형식이 잘못됐습니다.",
    "fh2-zero-buffering-not-modeled": "버퍼 시간 0초(무버퍼) 스트림은 이 규칙의 모형 밖입니다.",
    "fh2-partitions-unknown": "동적 파티셔닝을 쓰지만 활성 파티션 수를 모릅니다.",
    "fh2-object-count-unexplained": "관측된 일별 객체 수가 버퍼 설정과 유입량으로 설명되지 않습니다.",
    "fh2-size-closes-first": "버퍼 크기가 먼저 차서 버퍼 시간을 늘려도 객체 수가 줄지 않습니다.",
    "fh2-objects-large-enough": "평균 객체 크기가 기준 이상입니다.",
    "fh2-freshness-missing": "하류 소비자의 허용 신선도가 입력되지 않았습니다.",
    "fh2-freshness-limits-interval": "허용 신선도 때문에 버퍼 시간을 늘릴 수 없습니다.",
    "fh2-longer-interval-fewer-objects": "허용 신선도 안에서 버퍼 시간을 늘리면 작은 객체가 줄어듭니다.",
    "ath-format-unknown": "SerDe·입력 형식으로 테이블 형식을 판별할 수 없습니다.",
    "ath-too-few-queries": "판정에 필요한 성공 쿼리 수가 부족합니다.",
    "ath-mostly-minimum": "쿼리 스캔 중앙값이 10 MB 최소 과금 이하입니다.",
    "ath-already-pruned": "쿼리가 테이블의 일부만 읽고 있습니다.",
    "ath-conversion-volume-missing": "형식 변환 대상 월 수집량(과금 GB)이 입력되지 않았습니다.",
    "ath-conversion-not-worth": "형식 변환 요금이 예상 스캔 절감보다 큽니다.",
    "ath-row-format-full-scans": "행 기반 테이블을 쿼리마다 크게 스캔합니다.",
    "ath-file-stats-missing": "파일 수·평균 파일 크기가 입력되지 않았습니다.",
    "ath-files-large-enough": "평균 파일 크기가 기준 이상입니다.",
    "ath-all-at-minimum": "모든 쿼리가 10 MB 최소 과금 이하라 합치기로 비용이 줄지 않습니다.",
    "ath-compaction-cost-missing": "합치기 작업의 DPU-시간이 입력되지 않았습니다.",
    "ath-compaction-not-worth": "합치기 비용이 절감 상한보다 큽니다.",
    "ath-small-files-above-minimum": "작은 Parquet 파일이 10 MB를 넘는 스캔을 만들고 있습니다.",
    "sm-not-gpu": "GPU 인스턴스가 아닙니다.",
    "sm-long-running-unknown": "노트북 안에서 장시간 작업이 도는지 입력되지 않았습니다.",
    "sm-long-running-in-notebook": "노트북 안에서 장시간 작업이 돌고 있습니다.",
    "sm-activity-missing": "노트북의 GPU·커널 활동 자료가 없습니다.",
    "sm-rate-unverified": "이 인스턴스 유형의 서울 리전 요율이 요율 사본에 없습니다.",
    "sm-gpu-busy-enough": "켜진 시간 대비 GPU 사용 비율이 기준 이상입니다.",
    "sm-gpu-mostly-idle": "GPU 노트북이 켜진 시간의 대부분 동안 GPU를 쓰지 않습니다.",
    "sm-always-on-unknown": "엔드포인트의 상시 대기 요구가 입력되지 않았습니다.",
    "sm-always-on-required": "엔드포인트 상시 대기가 요구사항입니다.",
    "sm-cold-start-unknown": "콜드 스타트 허용 여부가 입력되지 않았습니다.",
    "sm-cold-start-not-acceptable": "콜드 스타트를 허용하지 않습니다.",
    "sm-gpu-serverless-unverified": "GPU 엔드포인트의 서버리스 대체 가능 여부를 확인하지 못했습니다.",
    "sm-serverless-not-cheaper": "서버리스 예상 비용이 기준만큼 낮지 않습니다.",
    "sm-endpoint-mostly-idle": "호출량에 비해 상시 엔드포인트 비용이 큽니다.",
    "cost-history-short": "기준선 계산에 필요한 이력이 부족합니다.",
    "cost-series-gap": "일별 비용 시계열에 빠진 날짜나 중복 날짜가 있습니다.",
    "cost-exclusion-without-cap": "경보일 제외 설정에 연속 경보 상한이 없습니다.",
}


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x >= 0


def load_ops_rates(thresholds):
    offers = load_json(ROOT / thresholds["rates_snapshot"])["offers"]
    first = lambda offer, ut: Decimal(next(r["usd"] for r in offers[offer]["rows"]
                                           if r["usagetype"] == ut and Decimal(r.get("begin") or 0) == 0))
    sm = {r["usagetype"]: Decimal(r["usd"]) for r in offers["AmazonSageMaker"]["rows"]}
    return {"s3_put": first("AmazonS3", "APN2-Requests-Tier1"), "s3_gb_month": first("AmazonS3", "APN2-TimedStorage-ByteHrs"),
            "athena_tb": first("AmazonAthena", "APN2-DataScannedInTB"),
            "conversion_gb": first("AmazonKinesisFirehose", "APN2-DFCBilledBytes"),
            "glue_etl_dpu_h": first("AWSGlue", "APN2-ETL-DPU-Hour"), "sagemaker": sm}


def _money(x):
    return str(Decimal(x).quantize(Decimal("0.0001")))


# ---------------------------------------------------------------- R-FH-2
def assess_buffer(s, thresholds, rates):
    item = s.get("DeliveryStreamName")
    used = ["firehose_buffer.max_interval_s", "firehose_buffer.small_object_bytes", "firehose_buffer.object_count_tolerance"]
    hints, dp, objs = s.get("BufferingHints"), s.get("dynamic_partitioning"), s.get("s3_objects_daily")
    if not (isinstance(item, str) and isinstance(hints, dict) and isinstance(dp, dict) and isinstance(objs, dict)
            and is_count(hints.get("SizeInMBs"), True) and is_count(hints.get("IntervalInSeconds"))
            and isinstance(dp.get("enabled"), bool) and is_count(s.get("IncomingBytes_daily_sum"), True)
            and is_count(objs.get("count"), True) and is_count(objs.get("mean_size_bytes"))):
        return decision("R-FH-2", item, "hold", ["input-invalid"], used=used)
    interval = hints["IntervalInSeconds"]
    if interval == 0:
        return decision("R-FH-2", item, "hold", ["fh2-zero-buffering-not-modeled"], used=used)
    parts = 1
    if dp["enabled"]:
        parts = dp.get("active_partitions")
        if not is_count(parts, True):
            return decision("R-FH-2", item, "hold", ["fh2-partitions-unknown"], used=used)
    rate = s["IncomingBytes_daily_sum"] / DAY_S / parts          # bytes per second per partition
    fill_s = hints["SizeInMBs"] * MIB / rate
    expected = parts * DAY_S / min(interval, fill_s)
    observed = objs["count"]
    evidence = {"partitions": parts, "seconds_to_fill_buffer": round(fill_s, 1),
                "objects_per_day_observed": observed, "objects_per_day_modeled": round(expected, 1),
                "mean_object_bytes": objs["mean_size_bytes"]}
    if abs(observed - expected) / expected > value(thresholds, "firehose_buffer", "object_count_tolerance"):
        return decision("R-FH-2", item, "hold", ["fh2-object-count-unexplained"], evidence, used=used)
    if fill_s <= interval:
        return decision("R-FH-2", item, "keep", ["fh2-size-closes-first"], evidence, used=used)
    if objs["mean_size_bytes"] >= value(thresholds, "firehose_buffer", "small_object_bytes"):
        return decision("R-FH-2", item, "keep", ["fh2-objects-large-enough"], evidence, used=used)
    fresh = s.get("allowed_freshness_s")
    if fresh is None:
        return decision("R-FH-2", item, "hold", ["fh2-freshness-missing"], evidence, used=used)
    if not is_count(fresh):
        return decision("R-FH-2", item, "hold", ["input-invalid"], used=used)
    proposed = int(min(value(thresholds, "firehose_buffer", "max_interval_s"), fresh, fill_s))
    if proposed <= interval:
        return decision("R-FH-2", item, "keep", ["fh2-freshness-limits-interval"], evidence, used=used)
    after = parts * DAY_S / proposed
    evidence.update({"proposed_interval_s": proposed, "objects_per_day_after": round(after, 1),
                     "mean_object_bytes_after": round(s["IncomingBytes_daily_sum"] / after),
                     "added_max_wait_s": proposed - interval})
    saving = Decimal(str((observed - after) * 30)) * rates["s3_put"]
    return decision("R-FH-2", item, "candidate", ["fh2-longer-interval-fewer-objects"], evidence, saving,
                    "월(30일), S3 PUT 요청만. 조회 단계의 GET·지연 변화는 미포함", used)


# ---------------------------------------------------------------- R-ATH-1 / R-ATH-2
ROW_SERDES = ("opencsvserde", "lazysimpleserde", "jsonserde", "json")


def table_format(table):
    sd = table.get("StorageDescriptor") or {}
    text = " ".join(str(x).lower() for x in (sd.get("InputFormat"), (sd.get("SerdeInfo") or {}).get("SerializationLibrary")))
    if "parquet" in text:
        return "parquet"
    if "orc" in text:
        return "orc"
    if any(k in text for k in ROW_SERDES):
        return "row"
    return None


def billed_mb(scan_bytes, minimum):
    return max(minimum, math.ceil(scan_bytes / MIB))


def assess_table(t, thresholds, rates):
    table = t.get("table") or {}
    item = table.get("Name")
    used = ["athena.min_billed_mb", "athena.min_queries"]
    runs = t.get("query_executions")
    if not (isinstance(item, str) and isinstance(runs, list) and is_count(t.get("observed_days"), True)
            and is_count(t.get("table_size_bytes"), True)):
        return decision("R-ATH", item, "hold", ["input-invalid"], used=used)
    scans = []
    for q in runs:
        try:
            state, kind = q["Status"]["State"], q["StatementType"]
            scanned = q["Statistics"]["DataScannedInBytes"]
        except (KeyError, TypeError):
            return decision("R-ATH", item, "hold", ["input-invalid"], used=used)
        if not is_count(scanned) or not isinstance(q.get("QueryExecutionId"), str):
            return decision("R-ATH", item, "hold", ["input-invalid"], used=used)
        if state == "SUCCEEDED" and kind == "DML":
            scans.append(scanned)
    fmt = table_format(table)
    rule = "R-ATH-1" if fmt == "row" else "R-ATH-2" if fmt in ("parquet", "orc") else "R-ATH"
    if fmt is None:
        return decision(rule, item, "hold", ["ath-format-unknown"], used=used)
    if len(scans) < value(thresholds, "athena", "min_queries"):
        return decision(rule, item, "hold", ["ath-too-few-queries"], {"successful_dml_queries": len(scans)}, used=used)
    minimum = value(thresholds, "athena", "min_billed_mb")
    per_tb = rates["athena_tb"] / (1024 * 1024)                      # USD per billed MB
    month = Decimal(30) / t["observed_days"]
    current = sum(billed_mb(b, minimum) for b in scans) * per_tb * month
    evidence = {"format": fmt, "successful_dml_queries": len(scans),
                "median_scan_bytes": statistics.median(scans),
                "median_billed_mb": billed_mb(statistics.median(scans), minimum),
                "athena_usd_month_observed": _money(current)}
    if rule == "R-ATH-1":
        used += ["athena.full_scan_share", "athena.parquet_scan_reduction"]
        if statistics.median(scans) <= minimum * MIB:
            return decision(rule, item, "keep", ["ath-mostly-minimum"], evidence, used=used)
        share = statistics.fmean(scans) / t["table_size_bytes"]
        evidence["mean_scan_share_of_table"] = round(share, 4)
        if share < value(thresholds, "athena", "full_scan_share"):
            return decision(rule, item, "keep", ["ath-already-pruned"], evidence, used=used)
        gb = t.get("conversion_billed_gb_month")
        if gb is None:
            return decision(rule, item, "hold", ["ath-conversion-volume-missing"], evidence, used=used)
        if not _num(gb):
            return decision(rule, item, "hold", ["input-invalid"], used=used)
        keep_share = 1 - value(thresholds, "athena", "parquet_scan_reduction")
        after = sum(billed_mb(b * keep_share, minimum) for b in scans) * per_tb * month
        conversion = Decimal(str(gb)) * rates["conversion_gb"]
        saving = current - after - conversion
        evidence.update({"athena_usd_month_after": _money(after), "conversion_usd_month": _money(conversion)})
        if saving <= 0:
            return decision(rule, item, "keep", ["ath-conversion-not-worth"], evidence, used=used)
        return decision(rule, item, "candidate", ["ath-row-format-full-scans"], evidence, saving,
                        "월, 018의 최소 감소율 91% 적용(로컬 대리 측정), 형식 변환 요금 차감", used)
    used += ["athena.small_file_bytes"]
    files = t.get("files")
    if not isinstance(files, dict):
        return decision(rule, item, "hold", ["ath-file-stats-missing"], evidence, used=used)
    if not (is_count(files.get("count"), True) and is_count(files.get("mean_size_bytes"))):
        return decision(rule, item, "hold", ["input-invalid"], used=used)
    evidence.update({"file_count": files["count"], "mean_file_bytes": files["mean_size_bytes"]})
    if files["mean_size_bytes"] >= value(thresholds, "athena", "small_file_bytes"):
        return decision(rule, item, "keep", ["ath-files-large-enough"], evidence, used=used)
    if max(scans) <= minimum * MIB:
        return decision(rule, item, "keep", ["ath-all-at-minimum"], evidence, used=used)
    comp = t.get("compaction")
    if not isinstance(comp, dict):
        return decision(rule, item, "hold", ["ath-compaction-cost-missing"], evidence, used=used)
    if not (_num(comp.get("dpu_hours_per_run")) and _num(comp.get("runs_per_month"))):
        return decision(rule, item, "hold", ["input-invalid"], used=used)
    upper = sum(billed_mb(b, minimum) - minimum for b in scans) * per_tb * month
    cost = Decimal(str(comp["dpu_hours_per_run"])) * Decimal(str(comp["runs_per_month"])) * rates["glue_etl_dpu_h"]
    evidence.update({"saving_upper_bound_usd_month": _money(upper), "compaction_usd_month": _money(cost)})
    if cost >= upper:
        return decision(rule, item, "keep", ["ath-compaction-not-worth"], evidence, used=used)
    return decision(rule, item, "candidate", ["ath-small-files-above-minimum"], evidence, upper - cost,
                    "월, 절감 상한(10 MB 초과 스캔 전부 제거 가정)에서 합치기 비용 차감", used)


# ---------------------------------------------------------------- R-SM-1
def _is_gpu(instance_type):
    return isinstance(instance_type, str) and instance_type.startswith(("ml.g", "ml.p"))


def assess_notebook(n, thresholds, rates):
    item = n.get("NotebookInstanceName")
    used = ["sagemaker.gpu_busy_share", "sagemaker.cpu_notebook_type", "sagemaker.hours_per_month"]
    intervals = n.get("status_intervals")
    if not (isinstance(item, str) and isinstance(n.get("InstanceType"), str) and is_count(n.get("VolumeSizeInGB"))
            and isinstance(intervals, list) and all(isinstance(i, dict) and isinstance(i.get("NotebookInstanceStatus"), str)
                                                    and _num(i.get("hours")) for i in intervals)
            and all(_num(n.get(k, 0)) for k in ("training_volume_gb", "s3_artifact_gb"))):
        return decision("R-SM-1", item, "hold", ["input-invalid"], used=used)
    kind = n["InstanceType"]
    if not _is_gpu(kind):
        return decision("R-SM-1", item, "keep", ["sm-not-gpu"], used=used)
    long_running = n.get("long_running_in_notebook")
    if long_running is None:
        return decision("R-SM-1", item, "hold", ["sm-long-running-unknown"], used=used)
    if long_running is True:
        return decision("R-SM-1", item, "keep", ["sm-long-running-in-notebook"], used=used)
    activity = n.get("activity") or {}
    busy = activity.get("gpu_busy_hours")
    basis = "gpu_busy_hours"
    if busy is None:
        busy, basis = activity.get("kernel_busy_hours"), "kernel_busy_hours (GPU 사용 상한으로 사용)"
    if busy is None:
        return decision("R-SM-1", item, "hold", ["sm-activity-missing"], used=used)
    in_service = sum(i["hours"] for i in intervals if i["NotebookInstanceStatus"] == "InService")
    if not _num(busy) or in_service <= 0 or busy > in_service:
        return decision("R-SM-1", item, "hold", ["input-invalid"], used=used)
    sm = rates["sagemaker"]
    cpu = value(thresholds, "sagemaker", "cpu_notebook_type")
    keys = (f"APN2-Notebk:{kind}", f"APN2-Train:{kind}", f"APN2-Notebk:{cpu}")
    if not all(k in sm for k in keys):
        return decision("R-SM-1", item, "hold", ["sm-rate-unverified"], used=used)
    share = busy / in_service
    evidence = {"in_service_hours": in_service, "busy_hours": busy, "busy_basis": basis, "busy_share": round(share, 4)}
    if share >= value(thresholds, "sagemaker", "gpu_busy_share"):
        return decision("R-SM-1", item, "keep", ["sm-gpu-busy-enough"], evidence, used=used)
    d = lambda x: Decimal(str(x))
    storage = d(n["VolumeSizeInGB"]) * sm["APN2-Notebk:VolumeUsage.gp2"] + d(n.get("s3_artifact_gb", 0)) * rates["s3_gb_month"]
    cpu_hours = n.get("proposed_cpu_notebook_hours", in_service)
    if not _num(cpu_hours):
        return decision("R-SM-1", item, "hold", ["input-invalid"], used=used)
    current = d(in_service) * sm[keys[0]] + storage
    train_storage = d(n.get("training_volume_gb", 0)) * sm["APN2-Train:VolumeUsage.gp2"] * d(busy) / d(value(thresholds, "sagemaker", "hours_per_month"))
    alternative = d(cpu_hours) * sm[keys[2]] + d(busy) * sm[keys[1]] + storage + train_storage
    evidence.update({"current_usd": _money(current), "alternative_usd": _money(alternative),
                     "current_to_alternative_ratio": str((current / alternative).quantize(Decimal("0.01"))),
                     "alternative": f"{cpu} {cpu_hours}h + {kind} 학습 작업 {busy}h"})
    return decision("R-SM-1", item, "candidate", ["sm-gpu-mostly-idle"], evidence, current - alternative,
                    "입력 기간, 노트북·학습 볼륨·S3 아티팩트 스토리지 포함", used)


def assess_endpoint(e, thresholds, rates):
    item = e.get("EndpointName")
    used = ["sagemaker.serverless_cost_share"]
    if not (isinstance(item, str) and isinstance(e.get("VariantName"), str) and isinstance(e.get("InstanceType"), str)
            and is_count(e.get("instance_count"), True) and _num(e.get("inservice_hours"))
            and is_count(e.get("Invocations_sum"))):
        return decision("R-SM-1", item, "hold", ["input-invalid"], used=used)
    for key, missing, blocking in (("always_on_required", "sm-always-on-unknown", "sm-always-on-required"),):
        if e.get(key) is None:
            return decision("R-SM-1", item, "hold", [missing], used=used)
        if e[key] is True:
            return decision("R-SM-1", item, "keep", [blocking], used=used)
    if e.get("cold_start_acceptable") is None:
        return decision("R-SM-1", item, "hold", ["sm-cold-start-unknown"], used=used)
    if e["cold_start_acceptable"] is not True:
        return decision("R-SM-1", item, "keep", ["sm-cold-start-not-acceptable"], used=used)
    if _is_gpu(e["InstanceType"]):
        return decision("R-SM-1", item, "hold", ["sm-gpu-serverless-unverified"], used=used)
    sm = rates["sagemaker"]
    host = sm.get(f"APN2-Host:{e['InstanceType']}")
    mem = e.get("serverless_memory_gb")
    serverless_rate = sm.get(f"APN2-ServerlessInf:Mem-{mem}GB") if is_count(mem, True) else None
    latency = e.get("ModelLatency_avg_us")
    if host is None or serverless_rate is None:
        return decision("R-SM-1", item, "hold", ["sm-rate-unverified"], used=used)
    if not _num(latency):
        return decision("R-SM-1", item, "hold", ["input-invalid"], used=used)
    d = lambda x: Decimal(str(x))
    current = d(e["instance_count"]) * d(e["inservice_hours"]) * host
    serverless = d(e["Invocations_sum"]) * d(latency) / 1_000_000 * serverless_rate
    evidence = {"endpoint_usd": _money(current), "serverless_usd": _money(serverless),
                "invocations": e["Invocations_sum"], "serverless_memory_gb": mem}
    if serverless >= current * d(value(thresholds, "sagemaker", "serverless_cost_share")):
        return decision("R-SM-1", item, "keep", ["sm-serverless-not-cheaper"], evidence, used=used)
    return decision("R-SM-1", item, "candidate", ["sm-endpoint-mostly-idle"], evidence, current - serverless,
                    "입력 기간, 서버리스 처리 시간 요금만(데이터 처리·콜드 스타트 영향 미포함)", used)


# ---------------------------------------------------------------- R-COST-1 (investigation queue)
def cost_series(series, thresholds):
    """Return (queue_items, hold_or_None) for one service's daily cost series."""
    service = series.get("service")
    window = value(thresholds, "cost", "window_days")
    k = value(thresholds, "cost", "mad_k")
    floor = value(thresholds, "cost", "min_relative_increase")
    exclude = value(thresholds, "cost", "exclude_alerts")
    cap = value(thresholds, "cost", "consecutive_cap_days")
    hold = lambda reason: {"rule": "R-COST-1", "service": service, "reason": reason, "message": REASONS[reason]}
    rows = series.get("ResultsByTime")
    metric = series.get("metric", "NetUnblendedCost")
    if not isinstance(service, str) or not isinstance(rows, list):
        return [], hold("input-invalid")
    if exclude and not is_count(cap, True):
        return [], hold("cost-exclusion-without-cap")
    days = []
    try:
        for r in rows:
            day = date.fromisoformat(r["TimePeriod"]["Start"])
            amount = Decimal(r["Metrics"][metric]["Amount"])
            if not amount.is_finite() or not isinstance(r.get("Estimated", False), bool):
                raise ValueError
            days.append((day, float(amount), r.get("Estimated", False)))
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return [], hold("input-invalid")
    days.sort()
    if any(b[0] - a[0] != timedelta(days=1) for a, b in zip(days, days[1:])):
        return [], hold("cost-series-gap")
    if len(days) <= window:
        return [], hold("cost-history-short")
    excluded, queue, streak = set(), [], 0
    for i in range(window, len(days)):
        history = [days[j][1] for j in range(i - 1, -1, -1) if j not in excluded][:window]
        if len(history) < window:
            continue
        m = statistics.median(history)
        mad = statistics.median(abs(v - m) for v in history)
        threshold = max(m + k * 1.4826 * mad, m * (1 + floor))
        x = days[i][1]
        if x > threshold and x - m > floor * m:
            streak += 1
            if exclude and streak <= cap:
                excluded.add(i)
            queue.append({"rule": "R-COST-1", "service": service, "date": days[i][0].isoformat(),
                          "observed_usd": f"{x:.2f}", "baseline_median_usd": f"{m:.2f}",
                          "threshold_usd": f"{threshold:.2f}", "estimated": days[i][2],
                          "consecutive_alert_days": streak})
        else:
            streak = 0
    return queue, None


def assess_ops(workloads, thresholds):
    rates = load_ops_rates(thresholds)
    out = [assess_buffer(s, thresholds, rates) for s in workloads.get("firehose_buffers", [])]
    out += [assess_table(t, thresholds, rates) for t in workloads.get("athena_tables", [])]
    out += [assess_notebook(n, thresholds, rates) for n in workloads.get("sagemaker_notebooks", [])]
    out += [assess_endpoint(e, thresholds, rates) for e in workloads.get("sagemaker_endpoints", [])]
    queue = holds = None
    if "daily_costs" in workloads:
        queue, holds = [], []
        for series in workloads["daily_costs"]:
            items, hold = cost_series(series, thresholds)
            queue += items
            if hold:
                holds.append(hold)
    return out, queue, holds
