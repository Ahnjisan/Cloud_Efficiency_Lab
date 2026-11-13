"""Convert raw AWS outputs into InfraFit workload input (read-only, standard library only).

Each converter reads files exactly as AWS returns them (aws CLI JSON, S3 Inventory
CSV, application-written Converse usage logs) and emits the workload sections that
infrafit/cli.py --workloads reads. Values a person has to supply (allowed
freshness, always-on requirement, notebook activity, query-to-table mapping) come
from a separate operations file; when they are missing the field is left empty so
InfraFit holds only that item. A bad field never stops the conversion: the item
is skipped or left incomplete and a warning is recorded under conversion.warnings.

Output contains only whitelisted fields. ARNs, account IDs, bucket names, S3
locations, query text and prompt bodies are never copied. --hash-names replaces
resource names and IDs with salted hashes for examples that may be shared.
"""
import argparse
import csv
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import sys

DAY_S = 86_400
PROMPT_KEYS = ("prompt", "messages", "system", "input", "output", "content", "text", "body")
GEOGRAPHIC_PREFIXES = ("us.", "eu.", "apac.", "jp.", "au.", "ca.", "us-gov.")


class Converter:
    def __init__(self, ops=None, hash_names=False, salt=""):
        self.ops = ops or {}
        self.hash_names = hash_names
        self.salt = salt
        self.warnings = []
        self.sources = defaultdict(int)

    # ------------------------------------------------------------ helpers
    def warn(self, source, file, item, code, field=None, action="skipped-item"):
        self.warnings.append({"source": source, "file": file, "item": self.name(item) if item else None,
                              "code": code, "field": field, "action": action})

    def name(self, raw):
        if not self.hash_names or raw is None:
            return raw
        return "h-" + hashlib.sha256(f"{self.salt}\0{raw}".encode("utf-8")).hexdigest()[:12]

    def ops_for(self, section, key):
        entry = (self.ops.get(section) or {}).get(key)
        return entry if isinstance(entry, dict) else {}

    # ------------------------------------------------------------ Cost Explorer
    def cost_explorer(self, pages):
        """GetCostAndUsage pages -> daily_costs (one series per SERVICE, NetUnblendedCost)."""
        metric = "NetUnblendedCost"
        rows, services = [], set()
        for file, page in pages:
            self.sources["cost_explorer"] += 1
            results = page.get("ResultsByTime") if isinstance(page, dict) else None
            if not isinstance(results, list):
                self.warn("cost_explorer", file, None, "field-missing", "ResultsByTime", "skipped-file")
                continue
            keys = [g.get("Key") for g in page.get("GroupDefinitions") or [] if isinstance(g, dict)]
            if keys and "SERVICE" not in keys:
                self.warn("cost_explorer", file, None, "group-by-without-service", "GroupDefinitions", "skipped-file")
                continue
            index = keys.index("SERVICE") if keys else None
            for row in results:
                try:
                    start = date.fromisoformat(row["TimePeriod"]["Start"])
                    end = row["TimePeriod"].get("End")
                except (KeyError, TypeError, ValueError):
                    self.warn("cost_explorer", file, None, "field-invalid", "ResultsByTime[].TimePeriod.Start")
                    continue
                amounts, unit = defaultdict(Decimal), "USD"
                groups = row.get("Groups") or []
                if index is None and not groups:
                    groups = [{"Keys": ["(total)"], "Metrics": row.get("Total") or {}}]
                for group in groups:
                    try:
                        service = group["Keys"][0 if index is None else index]
                        amount = Decimal(group["Metrics"][metric]["Amount"])
                        unit = group["Metrics"][metric].get("Unit", unit)
                    except (KeyError, TypeError, IndexError, InvalidOperation):
                        self.warn("cost_explorer", file, None, "field-missing", f"Groups[].Metrics.{metric}.Amount")
                        continue
                    amounts[service] += amount
                    services.add(service)
                rows.append((start, end, bool(row.get("Estimated", False)), amounts, unit))
        out = []
        for service in sorted(services):
            series = [{"TimePeriod": {"Start": s.isoformat(), "End": e or (s + timedelta(days=1)).isoformat()},
                       "Estimated": est, "Metrics": {metric: {"Amount": str(a.get(service, Decimal(0))), "Unit": u}}}
                      for s, e, est, a, u in rows]
            out.append({"service": service, "metric": metric, "ResultsByTime": series})
        if out and self.hash_names:
            self.warn("cost_explorer", None, None, "dates-and-amounts-kept", "ResultsByTime", "kept")
        return out

    # ------------------------------------------------------------ CloudWatch GetMetricData
    def metrics(self, query_docs, data_docs):
        """Pair MetricDataQueries with MetricDataResults by Id; return {(namespace, metric, dims): info}."""
        queries = {}
        span = {}
        for file, doc in query_docs:
            self.sources["metric_queries"] += 1
            start, end = _epoch(doc.get("StartTime")), _epoch(doc.get("EndTime"))
            for q in doc.get("MetricDataQueries") or []:
                stat = (q or {}).get("MetricStat") or {}
                metric = stat.get("Metric") or {}
                if not (isinstance(q.get("Id"), str) and metric.get("Namespace") and metric.get("MetricName")):
                    self.warn("cloudwatch", file, None, "query-without-metricstat", "MetricDataQueries[].MetricStat")
                    continue
                dims = tuple(sorted((d.get("Name"), d.get("Value")) for d in metric.get("Dimensions") or []))
                queries[q["Id"]] = (metric["Namespace"], metric["MetricName"], dims, stat.get("Stat"), stat.get("Period"))
                span[q["Id"]] = (start, end)
        series = defaultdict(lambda: {"points": {}, "status": set()})
        for file, doc in data_docs:
            self.sources["metric_data"] += 1
            for r in doc.get("MetricDataResults") or []:
                rid = (r or {}).get("Id")
                if rid not in queries:
                    self.warn("cloudwatch", file, rid, "result-without-query", "MetricDataResults[].Id")
                    continue
                ts, vals = r.get("Timestamps") or [], r.get("Values") or []
                if len(ts) != len(vals):
                    self.warn("cloudwatch", file, rid, "timestamps-values-mismatch", "MetricDataResults[].Values")
                    continue
                entry = series[rid]
                entry["status"].add(r.get("StatusCode"))
                for t, v in zip(ts, vals):
                    entry["points"][_epoch(t)] = v
        out = {}
        for rid, entry in series.items():
            namespace, metric, dims, stat, period = queries[rid]
            key = (namespace, metric, dims)
            if entry["status"] != {"Complete"}:
                self.warn("cloudwatch", None, _dim_name(dims), "status-not-complete", f"{metric}.StatusCode")
                continue
            out[key] = {"stat": stat, "period": period, "points": entry["points"], "span": span.get(rid)}
        return out

    # ------------------------------------------------------------ S3 Inventory
    def inventory(self, manifests):
        """manifest.json (+ its CSV files next to it) -> list of (key, size, last_modified, creation_date)."""
        objects = []
        for file, manifest in manifests:
            self.sources["s3_inventory"] += 1
            fmt = manifest.get("fileFormat")
            if fmt != "CSV":
                self.warn("s3_inventory", file, None, "format-not-supported", f"fileFormat={fmt}", "skipped-file")
                continue
            schema = [c.strip() for c in str(manifest.get("fileSchema", "")).split(",")]
            if not {"Key", "Size", "LastModifiedDate"} <= set(schema):
                self.warn("s3_inventory", file, None, "field-missing", "fileSchema Key/Size/LastModifiedDate", "skipped-file")
                continue
            created = _epoch(manifest.get("creationTimestamp"), millis=True)
            created_day = datetime.fromtimestamp(created, timezone.utc).date() if created else None
            base = Path(file).parent
            for f in manifest.get("files") or []:
                local = base / Path(str(f.get("key", ""))).name
                try:
                    raw = local.read_bytes()
                except OSError:
                    self.warn("s3_inventory", file, None, "data-file-missing", "files[].key", "skipped-file")
                    continue
                text = gzip.decompress(raw).decode("utf-8") if raw[:2] == b"\x1f\x8b" else raw.decode("utf-8")
                for rec in csv.reader(io.StringIO(text)):
                    row = dict(zip(schema, rec))
                    try:
                        modified = datetime.fromisoformat(row["LastModifiedDate"].replace("Z", "+00:00"))
                        objects.append((row["Key"], int(row["Size"]), modified, created_day))
                    except (KeyError, ValueError):
                        self.warn("s3_inventory", file, None, "row-invalid", "Size/LastModifiedDate")
        return objects

    @staticmethod
    def prefix_stats(objects, prefix):
        hits = [o for o in objects if o[0].startswith(prefix)]
        if not hits:
            return None
        total = sum(o[1] for o in hits)
        created = next((o[3] for o in hits if o[3]), None)
        full = [o for o in hits if o[2].date() != created]
        days = sorted({o[2].date() for o in full})
        daily = None
        if days:
            n_days = (days[-1] - days[0]).days + 1
            daily = {"count": round(len(full) / n_days), "mean_size_bytes": round(sum(o[1] for o in full) / len(full)),
                     "days": n_days}
        return {"count": len(hits), "total_bytes": total, "mean_size_bytes": round(total / len(hits)), "daily": daily}

    # ------------------------------------------------------------ Firehose
    def firehose(self, describes, metric_series, objects):
        out = []
        for file, doc in describes:
            self.sources["firehose_describe"] += 1
            desc = (doc or {}).get("DeliveryStreamDescription") or {}
            name = desc.get("DeliveryStreamName")
            if not isinstance(name, str):
                self.warn("firehose", file, None, "field-missing", "DeliveryStreamDescription.DeliveryStreamName")
                continue
            s3 = next((d.get("ExtendedS3DestinationDescription") for d in desc.get("Destinations") or []
                       if isinstance(d, dict) and d.get("ExtendedS3DestinationDescription")), None)
            hints = (s3 or {}).get("BufferingHints") or {}
            if not s3 or not isinstance(hints.get("SizeInMBs"), int) or not isinstance(hints.get("IntervalInSeconds"), int):
                self.warn("firehose", file, name, "destination-not-supported", "Destinations[].ExtendedS3DestinationDescription.BufferingHints")
                continue
            enabled = ((s3.get("DynamicPartitioningConfiguration") or {}).get("Enabled")) is True
            ops = self.ops_for("firehose", name)
            daily_bytes = None
            m = metric_series.get(("AWS/Firehose", "IncomingBytes", (("DeliveryStreamName", name),)))
            if m is None:
                self.warn("firehose", file, name, "metric-missing", "IncomingBytes", "left-null")
            elif m["stat"] != "Sum":
                self.warn("firehose", file, name, "stat-not-sum", "IncomingBytes.Stat", "left-null")
            else:
                days = _span_days(m)
                daily_bytes = round(sum(m["points"].values()) / days) if days else None
            objs = None
            prefix = ops.get("s3_prefix")
            stats = self.prefix_stats(objects, prefix) if isinstance(prefix, str) else None
            if stats and stats["daily"]:
                objs = {"count": stats["daily"]["count"], "mean_size_bytes": stats["daily"]["mean_size_bytes"]}
            else:
                self.warn("firehose", file, name, "inventory-missing", "s3_objects_daily", "left-null")
            for key in ("allowed_freshness_s",) + (("active_partitions",) if enabled else ()):
                if ops.get(key) is None:
                    self.warn("firehose", file, name, "ops-value-missing", key, "left-null")
            out.append({"DeliveryStreamName": self.name(name),
                        "BufferingHints": {"SizeInMBs": hints["SizeInMBs"], "IntervalInSeconds": hints["IntervalInSeconds"]},
                        "dynamic_partitioning": {"enabled": enabled, "active_partitions": ops.get("active_partitions")},
                        "IncomingBytes_daily_sum": daily_bytes, "s3_objects_daily": objs,
                        "allowed_freshness_s": ops.get("allowed_freshness_s")})
        return out

    # ------------------------------------------------------------ Athena + Glue
    def athena(self, query_docs, table_docs, objects):
        mapping = (self.ops.get("athena") or {}).get("queries") or {}
        by_table = defaultdict(list)
        for file, doc in query_docs:
            self.sources["athena_queries"] += 1
            for u in (doc or {}).get("UnprocessedQueryExecutionIds") or []:
                self.warn("athena", file, (u or {}).get("QueryExecutionId"), "unprocessed-query", "UnprocessedQueryExecutionIds")
            for q in (doc or {}).get("QueryExecutions") or []:
                qid = (q or {}).get("QueryExecutionId")
                status, stats = q.get("Status") or {}, q.get("Statistics") or {}
                scanned = stats.get("DataScannedInBytes")
                if not isinstance(qid, str) or not isinstance(status.get("State"), str) or not isinstance(q.get("StatementType"), str):
                    self.warn("athena", file, qid, "field-missing", "QueryExecutionId/Status.State/StatementType")
                    continue
                if not isinstance(scanned, int) or isinstance(scanned, bool):
                    self.warn("athena", file, qid, "field-missing", "Statistics.DataScannedInBytes")
                    continue
                table = mapping.get(qid)
                if table is None:
                    self.warn("athena", file, qid, "query-table-unknown", "ops.athena.queries")
                    continue
                submitted = _epoch(status.get("SubmissionDateTime"))
                by_table[table].append((qid, q["StatementType"], status["State"], scanned, submitted))
        out = []
        for file, doc in table_docs:
            self.sources["glue_tables"] += 1
            t = (doc or {}).get("Table") or {}
            name = t.get("Name")
            sd = t.get("StorageDescriptor") or {}
            if not isinstance(name, str) or not isinstance(sd, dict):
                self.warn("athena", file, None, "field-missing", "Table.Name/StorageDescriptor")
                continue
            tables = (self.ops.get("athena") or {}).get("tables") or {}
            ops = tables.get(name) if isinstance(tables.get(name), dict) else {}
            runs = by_table.get(name, [])
            stamps = [r[4] for r in runs if r[4] is not None]
            observed = ops.get("observed_days")
            if observed is None and stamps:
                first, last = (datetime.fromtimestamp(x, timezone.utc).date() for x in (min(stamps), max(stamps)))
                observed = (last - first).days + 1
            if observed is None:
                self.warn("athena", file, name, "observed-days-unknown", "Status.SubmissionDateTime", "left-null")
            stats = self.prefix_stats(objects, ops["s3_prefix"]) if isinstance(ops.get("s3_prefix"), str) else None
            size = ops.get("table_size_bytes", stats["total_bytes"] if stats else None)
            if size is None:
                self.warn("athena", file, name, "table-size-missing", "table_size_bytes", "left-null")
            files = {"count": stats["count"], "mean_size_bytes": stats["mean_size_bytes"]} if stats else ops.get("files")
            executions = []
            for qid, kind, state, scanned, submitted in runs:
                q = {"QueryExecutionId": self.name(qid), "StatementType": kind, "Status": {"State": state},
                     "Statistics": {"DataScannedInBytes": scanned}}
                if submitted is not None and not self.hash_names:
                    q["Status"]["SubmissionDateTime"] = _iso(submitted)
                executions.append(q)
            serde = (sd.get("SerdeInfo") or {}).get("SerializationLibrary")
            out.append({"table": {"Name": self.name(name),
                                  "StorageDescriptor": {"InputFormat": sd.get("InputFormat"),
                                                        "SerdeInfo": {"SerializationLibrary": serde},
                                                        "Compressed": sd.get("Compressed")},
                                  "PartitionKeys": [{"Name": p.get("Name")}
                                                    for p in t.get("PartitionKeys") or [] if isinstance(p, dict)]},
                        "table_size_bytes": size, "observed_days": observed, "query_executions": executions,
                        "conversion_billed_gb_month": ops.get("conversion_billed_gb_month"),
                        "files": files, "compaction": ops.get("compaction")})
        return out

    # ------------------------------------------------------------ SageMaker
    def notebooks(self, docs):
        out = []
        for file, doc in docs:
            self.sources["sagemaker_notebook"] += 1
            name = (doc or {}).get("NotebookInstanceName")
            if not isinstance(name, str) or not isinstance(doc.get("InstanceType"), str):
                self.warn("sagemaker", file, name, "field-missing", "NotebookInstanceName/InstanceType")
                continue
            ops = self.ops_for("sagemaker_notebooks", name)
            for key in ("status_intervals", "activity", "long_running_in_notebook"):
                if ops.get(key) is None:
                    self.warn("sagemaker", file, name, "ops-value-missing", key, "left-null")
            item = {"NotebookInstanceName": self.name(name), "InstanceType": doc["InstanceType"],
                    "VolumeSizeInGB": doc.get("VolumeSizeInGB"), "status_intervals": ops.get("status_intervals"),
                    "activity": ops.get("activity"), "long_running_in_notebook": ops.get("long_running_in_notebook")}
            for key in ("proposed_cpu_notebook_hours", "training_volume_gb", "s3_artifact_gb"):
                if key in ops:
                    item[key] = ops[key]
            out.append(item)
        return out

    def endpoints(self, docs, metric_series):
        configs, endpoints = {}, []
        for file, doc in docs:
            self.sources["sagemaker_endpoint"] += 1
            if isinstance(doc, dict) and "EndpointName" in doc:
                endpoints.append((file, doc))
            elif isinstance(doc, dict) and "EndpointConfigName" in doc:
                configs[doc["EndpointConfigName"]] = doc
        out = []
        for file, ep in endpoints:
            name = ep["EndpointName"]
            config = configs.get(ep.get("EndpointConfigName"))
            if config is None:
                self.warn("sagemaker", file, name, "endpoint-config-missing", "EndpointConfigName")
                continue
            current = {v.get("VariantName"): v for v in ep.get("ProductionVariants") or [] if isinstance(v, dict)}
            ops = self.ops_for("sagemaker_endpoints", name)
            for variant in config.get("ProductionVariants") or []:
                vname = (variant or {}).get("VariantName")
                if not isinstance(variant.get("InstanceType"), str):
                    self.warn("sagemaker", file, name, "variant-not-instance-based", "ProductionVariants[].InstanceType")
                    continue
                count = (current.get(vname) or {}).get("CurrentInstanceCount", variant.get("InitialInstanceCount"))
                dims = (("EndpointName", name), ("VariantName", vname))
                inv = metric_series.get(("AWS/SageMaker", "Invocations", dims))
                lat = metric_series.get(("AWS/SageMaker", "ModelLatency", dims))
                invocations = round(sum(inv["points"].values())) if inv and inv["stat"] == "Sum" else None
                latency = None
                if lat and lat["stat"] == "Average" and lat["points"]:
                    weights = inv["points"] if inv else {}
                    shared = [t for t in lat["points"] if weights.get(t)]
                    if shared:
                        latency = sum(lat["points"][t] * weights[t] for t in shared) / sum(weights[t] for t in shared)
                    else:
                        latency = sum(lat["points"].values()) / len(lat["points"])
                        self.warn("sagemaker", file, name, "latency-unweighted", "ModelLatency", "kept")
                    latency = round(latency)
                if invocations is None:
                    self.warn("sagemaker", file, name, "metric-missing", "Invocations", "left-null")
                if latency is None:
                    self.warn("sagemaker", file, name, "metric-missing", "ModelLatency", "left-null")
                for key in ("inservice_hours", "always_on_required", "cold_start_acceptable", "serverless_memory_gb"):
                    if ops.get(key) is None:
                        self.warn("sagemaker", file, name, "ops-value-missing", key, "left-null")
                out.append({"EndpointName": self.name(name), "VariantName": self.name(vname),
                            "InstanceType": variant["InstanceType"], "instance_count": count,
                            "inservice_hours": ops.get("inservice_hours"), "Invocations_sum": invocations,
                            "ModelLatency_avg_us": latency, "always_on_required": ops.get("always_on_required"),
                            "cold_start_acceptable": ops.get("cold_start_acceptable"),
                            "serverless_memory_gb": ops.get("serverless_memory_gb")})
        return out

    # ------------------------------------------------------------ Bedrock (application Converse usage log)
    def bedrock(self, files):
        calls = []
        overrides = self.ops.get("bedrock_models") or {}
        for file, lines in files:
            self.sources["bedrock_usage"] += 1
            for number, line in enumerate(lines, 1):
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    self.warn("bedrock", file, f"line {number}", "line-invalid", None)
                    continue
                dropped = [k for k in rec if k.lower() in PROMPT_KEYS]
                if dropped:
                    self.warn("bedrock", file, f"line {number}", "prompt-field-dropped", ",".join(sorted(dropped)), "dropped-field")
                usage = rec.get("usage") or {}
                model_id, run_id = rec.get("modelId"), rec.get("run_id")
                ts = _epoch(rec.get("timestamp"))
                counts = [usage.get(k, 0) for k in ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheWriteInputTokens")]
                if not (isinstance(model_id, str) and isinstance(run_id, str) and ts is not None
                        and isinstance(rec.get("prefix_hash"), str) and _count(rec.get("prefix_tokens"))
                        and _count(usage.get("inputTokens")) and all(_count(c) for c in counts)):
                    self.warn("bedrock", file, f"line {number}", "field-missing",
                              "modelId/run_id/timestamp/prefix_hash/prefix_tokens/usage.inputTokens")
                    continue
                model, profile = model_and_profile(model_id, overrides)
                ttl = rec.get("cache_ttl")
                details = [d.get("ttl") for d in usage.get("cacheDetails") or [] if isinstance(d, dict)]
                if ttl is None and len(set(details)) == 1:
                    ttl = details[0]
                if ttl is None and (counts[2] or counts[3]):
                    self.warn("bedrock", file, f"line {number}", "cache-ttl-unknown", "cache_ttl", "left-null")
                calls.append({"call_id": rec.get("call_id") or f"{run_id}-{number}", "run_id": run_id, "model": model,
                              "profile": profile, "prefix_hash": rec["prefix_hash"], "prefix_tokens": rec["prefix_tokens"],
                              "input_tokens": counts[0], "cache_read_tokens": counts[2], "cache_write_tokens": counts[3],
                              "cache_ttl": ttl, "output_tokens": counts[1], "ts": ts})
        if self.hash_names and calls:
            origin = min(c["ts"] for c in calls)
            for c in calls:
                c.update(call_id=self.name(c["call_id"]), run_id=self.name(c["run_id"]),
                         prefix_hash=self.name(c["prefix_hash"]), ts=c["ts"] - origin)
        return calls


def model_and_profile(model_id, overrides):
    """'global.anthropic.claude-haiku-5-5' -> ('Claude Haiku 5.5', 'global'). Overrides win."""
    if isinstance(overrides.get(model_id), dict):
        o = overrides[model_id]
        return o.get("model", model_id), o.get("profile", "in-region")
    profile, base = "in-region", model_id
    if model_id.startswith("global."):
        profile, base = "global", model_id[len("global."):]
    else:
        for p in GEOGRAPHIC_PREFIXES:
            if model_id.startswith(p):
                profile, base = "geographic", model_id[len(p):]
                break
    if base.startswith("anthropic.claude-"):
        parts = base[len("anthropic.claude-"):].split(":")[0].split("-")
        family = parts[0]
        version = [p for p in parts[1:] if p.isdigit() and len(p) <= 2]
        if version:
            return f"Claude {family.capitalize()} {'.'.join(version)}", profile
    return base, profile


def _count(x):
    return isinstance(x, int) and not isinstance(x, bool) and x >= 0


def _epoch(x, millis=False):
    if x is None or isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return x / 1000 if millis else x
    if isinstance(x, str):
        try:
            return float(x) / 1000 if millis else float(x)
        except ValueError:
            pass
        try:
            d = datetime.fromisoformat(x.replace("Z", "+00:00"))
        except ValueError:
            return None
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()
    return None


def _iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _span_days(m):
    start, end = m.get("span") or (None, None)
    if start is not None and end is not None and end > start:
        return max(1, math.floor((end - start) / DAY_S))
    if m.get("period") == DAY_S:
        return len(m["points"]) or None
    return None


def _dim_name(dims):
    return next((v for k, v in dims if k in ("DeliveryStreamName", "EndpointName")), None)


def _read_json(path, conv, source):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        conv.warn(source, Path(path).name, None, "file-unreadable", None, "skipped-file")
        return None


def convert(args):
    ops = {}
    conv = Converter(hash_names=args.hash_names, salt=args.hash_salt or "")
    if args.ops_info:
        ops = _read_json(args.ops_info, conv, "ops_info") or {}
        conv.ops = ops
    if args.hash_names and not args.hash_salt:
        conv.warn("hash", None, None, "salt-missing", "--hash-salt", "kept")

    def load(paths, source):
        docs = []
        for p in paths or []:
            doc = _read_json(p, conv, source)
            if doc is not None:
                docs.append((str(p), doc))
        return docs

    objects = conv.inventory(load(args.s3_inventory, "s3_inventory"))
    metric_series = conv.metrics(load(args.metric_queries, "cloudwatch"), load(args.metric_data, "cloudwatch"))
    out = {"data_kind": args.data_kind,
           "note": "Converted from AWS outputs by infrafit/convert.py. Values marked as human input come from the operations file."}
    sections = {
        "daily_costs": conv.cost_explorer(load(args.cost_explorer, "cost_explorer")),
        "firehose_buffers": conv.firehose(load(args.firehose_describe, "firehose"), metric_series, objects),
        "athena_tables": conv.athena(load(args.athena_queries, "athena"), load(args.glue_table, "athena"), objects),
        "sagemaker_notebooks": conv.notebooks(load(args.sagemaker_notebook, "sagemaker")),
        "sagemaker_endpoints": conv.endpoints(load(args.sagemaker_endpoint, "sagemaker"), metric_series),
    }
    lines = []
    for p in args.bedrock_usage or []:
        try:
            lines.append((str(p), Path(p).read_text(encoding="utf-8").splitlines()))
        except OSError:
            conv.warn("bedrock", Path(p).name, None, "file-unreadable", None, "skipped-file")
    sections["bedrock_calls"] = conv.bedrock(lines)
    out.update({k: v for k, v in sections.items() if v})
    for w in conv.warnings:  # never leak local paths
        if w["file"]:
            w["file"] = Path(w["file"]).name
    out["conversion"] = {"sources": dict(sorted(conv.sources.items())), "hashed": args.hash_names,
                         "warnings": conv.warnings}
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--cost-explorer", nargs="+", type=Path, help="GetCostAndUsage responses (pages)")
    p.add_argument("--athena-queries", nargs="+", type=Path, help="BatchGetQueryExecution responses")
    p.add_argument("--glue-table", nargs="+", type=Path, help="Glue GetTable responses")
    p.add_argument("--metric-queries", nargs="+", type=Path, help="GetMetricData request files (MetricDataQueries)")
    p.add_argument("--metric-data", nargs="+", type=Path, help="GetMetricData responses")
    p.add_argument("--firehose-describe", nargs="+", type=Path, help="DescribeDeliveryStream responses")
    p.add_argument("--s3-inventory", nargs="+", type=Path, help="S3 Inventory manifest.json files (CSV data next to them)")
    p.add_argument("--sagemaker-notebook", nargs="+", type=Path, help="DescribeNotebookInstance responses")
    p.add_argument("--sagemaker-endpoint", nargs="+", type=Path, help="DescribeEndpoint and DescribeEndpointConfig responses")
    p.add_argument("--bedrock-usage", nargs="+", type=Path, help="application Converse usage logs (JSON Lines)")
    p.add_argument("--ops-info", type=Path, help="human-supplied operations values and mappings")
    p.add_argument("--hash-names", action="store_true", help="replace resource names and IDs with salted hashes")
    p.add_argument("--hash-salt", help="secret salt for --hash-names (keep it outside the repository)")
    p.add_argument("--data-kind", default="real", choices=("real", "synthetic"))
    p.add_argument("--out", type=Path, help="output path (default: stdout)")
    args = p.parse_args(argv)
    result = convert(args)
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")
    print(f"converted: {', '.join(k for k in result if isinstance(result[k], list)) or 'nothing'}; "
          f"warnings: {len(result['conversion']['warnings'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
