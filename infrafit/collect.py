"""Collect the AWS files infrafit/convert.py reads, read-only, into a folder outside the repository.

Calls only the aws CLI with a read-only profile (default cel-readonly) and only
the actions in experiments/real-account/cel-readonly-policy.json (plus s3 cp for an
S3 Inventory the person names). Nothing is created, changed or deleted.

Phases:
  1. --dry-run: no AWS call at all. Prints the APIs that would be called, the caps
     and the worst-case cost.
  2. free phase: list/describe calls (Firehose, Athena, Glue, SageMaker). Glue
     catalog requests are metered but the first million per month are free.
  3. paid phase (Cost Explorer, GetMetricData, S3 Inventory GET): the exact plan is
     printed first; it runs only with --yes and only within the caps.
Raw responses, requests.log and collect-summary.json stay in --out. The summary has
counts and costs only, no resource names.
"""
import argparse
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SERVICES = ("cost", "firehose", "athena", "sagemaker", "cloudwatch", "s3-inventory")
DEFAULT_SERVICES = ("cost", "firehose", "athena", "sagemaker", "cloudwatch")
BATCH = 50          # BatchGetQueryExecution maximum
METRICS_PER_CALL = 500  # GetMetricData maximum MetricDataQueries


def _snapshot_rate(offer, usagetype):
    snap = json.loads((REPO / "references" / "aws-price-list-apn2-2026-11-13.json").read_text(encoding="utf-8"))
    return Decimal(next(r["usd"] for r in snap["offers"][offer]["rows"] if r["usagetype"] == usagetype))


RATES = {
    "cost_explorer_request": {"usd": Decimal("0.01"), "unit": "request",
                              "source": "AWS Cost Explorer pricing page, checked 2026-11-13"},
    "get_metric_data_metric": {"usd": Decimal("0.00001"), "unit": "metric requested",
                               "source": "AWS Price List AmazonCloudWatch ap-northeast-2 ($0.01/1,000), checked 2026-11-13; "
                                         "always charged, not in the free API tier (CloudWatch pricing page, 2026-11-14)"},
    "s3_get_request": {"usd": _snapshot_rate("AmazonS3", "APN2-Requests-Tier2"), "unit": "GET request",
                       "source": "references/aws-price-list-apn2-2026-11-13.json APN2-Requests-Tier2"},
    "glue_catalog_request": {"usd": _snapshot_rate("AWSGlue", "APN2-Catalog-Request"), "unit": "request",
                             "source": "references/aws-price-list-apn2-2026-11-13.json APN2-Catalog-Request; "
                                       "first 1M requests/month free (AWS Glue pricing page, 2026-11-14)"},
}
def usd(x):
    return format(Decimal(x).quantize(Decimal("0.000001")), "f")


SECRET = re.compile(r"arn:aws[^\s\"']*|\b\d{12}\b")


class Collector:
    def __init__(self, args):
        self.args = args
        self.out = args.out
        if args.aws_cmd and args.aws_cmd.startswith("["):
            self.aws = json.loads(args.aws_cmd)
        else:
            self.aws = shlex.split(args.aws_cmd) if args.aws_cmd else ["aws"]
        self.calls = {}
        self.paid = {"cost_explorer_requests": 0, "get_metric_data_metrics": 0, "s3_get_requests": 0,
                     "glue_catalog_requests": 0}
        self.counts = {}
        self.files = []
        self.warnings = []
        self.log = []

    # ------------------------------------------------------------ aws CLI
    def aws_call(self, service, op, params, region=None, out_file=None):
        cmd = [*self.aws, service, op, *params, "--profile", self.args.profile,
               "--region", region or self.args.region, "--output", "json"]
        key = f"{service} {op}"
        self.calls[key] = self.calls.get(key, 0) + 1
        self.log.append(" ".join([service, op, *params]))
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if proc.returncode != 0:
            first = (proc.stderr.strip().splitlines() or [""])[0]
            self.warnings.append({"api": key, "code": "aws-error", "exit": proc.returncode,
                                  "message": SECRET.sub("<redacted>", first)[:200]})
            return None
        if service == "s3":
            return True
        try:
            doc = json.loads(proc.stdout or "{}")
        except ValueError:
            self.warnings.append({"api": key, "code": "not-json"})
            return None
        if out_file:
            self.save(out_file, doc)
        return doc

    def save(self, name, doc):
        path = self.out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.files.append(name)

    # ------------------------------------------------------------ free phase
    def firehose(self):
        names, start = [], None
        while True:
            params = ["--limit", "100"] + (["--exclusive-start-delivery-stream-name", start] if start else [])
            doc = self.aws_call("firehose", "list-delivery-streams", params)
            if not doc:
                break
            names += doc.get("DeliveryStreamNames") or []
            if not doc.get("HasMoreDeliveryStreams") or not names:
                break
            start = names[-1]
        self.streams = []
        for i, name in enumerate(names):
            doc = self.aws_call("firehose", "describe-delivery-stream", ["--delivery-stream-name", name],
                                out_file=f"firehose-{i:03d}.json")
            if doc:
                self.streams.append(name)
        self.counts["firehose_streams"] = len(self.streams)

    def athena(self):
        start, end = (datetime.combine(d, datetime.min.time(), timezone.utc) for d in (self.args.start, self.args.end))
        ids = []
        groups = self.aws_call("athena", "list-work-groups", []) or {}
        for g in groups.get("WorkGroups") or []:
            doc = self.aws_call("athena", "list-query-executions",
                                ["--work-group", g["Name"], "--max-items", str(self.args.max_athena_queries)])
            ids += (doc or {}).get("QueryExecutionIds") or []
        kept = outside = 0
        for n in range(0, len(ids), BATCH):
            doc = self.aws_call("athena", "batch-get-query-execution",
                                ["--query-execution-ids", *ids[n:n + BATCH]])
            if not doc:
                continue
            inside = []
            for q in doc.get("QueryExecutions") or []:
                when = _parse_time((q.get("Status") or {}).get("SubmissionDateTime"))
                if when is not None and start <= when < end:
                    inside.append(q)
                else:
                    outside += 1
            kept += len(inside)
            doc["QueryExecutions"] = inside
            self.save(f"athena-queries-{n // BATCH:03d}.json", doc)
        self.counts["athena_queries_in_period"] = kept
        self.counts["athena_queries_outside_period"] = outside
        tables = 0
        for db in self.args.glue_databases or []:
            doc = self.aws_call("glue", "get-tables", ["--database-name", db])
            self.paid["glue_catalog_requests"] += 1
            for t in (doc or {}).get("TableList") or []:
                self.save(f"glue-table-{tables:03d}.json", {"Table": t})
                tables += 1
        self.counts["glue_tables"] = tables
        if not self.args.glue_databases:
            self.warnings.append({"api": "glue get-tables", "code": "no-glue-databases",
                                  "message": "--glue-databases not given; Athena tables cannot be converted"})

    def sagemaker(self):
        doc = self.aws_call("sagemaker", "list-notebook-instances", []) or {}
        notebooks = [n["NotebookInstanceName"] for n in doc.get("NotebookInstances") or []]
        for i, name in enumerate(notebooks):
            self.aws_call("sagemaker", "describe-notebook-instance", ["--notebook-instance-name", name],
                          out_file=f"notebook-{i:03d}.json")
        doc = self.aws_call("sagemaker", "list-endpoints", []) or {}
        self.variants = []
        for i, ep in enumerate(e["EndpointName"] for e in doc.get("Endpoints") or []):
            d = self.aws_call("sagemaker", "describe-endpoint", ["--endpoint-name", ep], out_file=f"endpoint-{i:03d}.json")
            if not d:
                continue
            self.aws_call("sagemaker", "describe-endpoint-config", ["--endpoint-config-name", d["EndpointConfigName"]],
                          out_file=f"endpoint-config-{i:03d}.json")
            self.variants += [(ep, v["VariantName"]) for v in d.get("ProductionVariants") or []]
        self.counts["sagemaker_notebooks"] = len(notebooks)
        self.counts["sagemaker_endpoint_variants"] = len(self.variants)

    # ------------------------------------------------------------ paid phase
    def metric_queries(self):
        queries = []
        for name in getattr(self, "streams", []):
            queries.append(("AWS/Firehose", "IncomingBytes", [("DeliveryStreamName", name)], "Sum"))
        for ep, variant in getattr(self, "variants", []):
            dims = [("EndpointName", ep), ("VariantName", variant)]
            queries += [("AWS/SageMaker", "Invocations", dims, "Sum"), ("AWS/SageMaker", "ModelLatency", dims, "Average")]
        return [{"Id": f"m{i}", "MetricStat": {"Metric": {"Namespace": ns, "MetricName": m,
                                                          "Dimensions": [{"Name": k, "Value": v} for k, v in dims]},
                                               "Period": 86400, "Stat": stat}}
                for i, (ns, m, dims, stat) in enumerate(queries)]

    def paid_plan(self):
        s = set(self.args.services)
        plan = {"cost_explorer_requests_max": self.args.max_ce_requests if "cost" in s else 0,
                "get_metric_data_metrics": len(self.metric_queries()) if "cloudwatch" in s else 0,
                "s3_inventory": bool(self.args.inventory_manifest) and "s3-inventory" in s}
        plan["estimated_usd_max"] = usd(
            plan["cost_explorer_requests_max"] * RATES["cost_explorer_request"]["usd"]
            + plan["get_metric_data_metrics"] * RATES["get_metric_data_metric"]["usd"])
        return plan

    def cost(self):
        token, page = None, 0
        while page < self.args.max_ce_requests:
            params = ["--time-period", f"Start={self.args.start},End={self.args.end}", "--granularity", "DAILY",
                      "--metrics", "NetUnblendedCost", "UsageQuantity", "--group-by", "Type=DIMENSION,Key=SERVICE"]
            if token:
                params += ["--next-page-token", token]
            self.paid["cost_explorer_requests"] += 1
            doc = self.aws_call("ce", "get-cost-and-usage", params, region="us-east-1", out_file=f"ce-page-{page:03d}.json")
            page += 1
            token = (doc or {}).get("NextPageToken")
            if not token:
                return
        self.warnings.append({"api": "ce get-cost-and-usage", "code": "pages-truncated-at-cap",
                              "message": f"stopped after {self.args.max_ce_requests} requests with more pages left"})

    def cloudwatch(self):
        queries = self.metric_queries()
        start = datetime.combine(self.args.start, datetime.min.time(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end = datetime.combine(self.args.end, datetime.min.time(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for n in range(0, len(queries), METRICS_PER_CALL):
            chunk = queries[n:n + METRICS_PER_CALL]
            request = {"StartTime": start, "EndTime": end, "MetricDataQueries": chunk, "ScanBy": "TimestampAscending"}
            name = f"metric-queries-{n // METRICS_PER_CALL:03d}.json"
            self.save(name, request)
            self.paid["get_metric_data_metrics"] += len(chunk)
            self.aws_call("cloudwatch", "get-metric-data", ["--cli-input-json", f"file://{(self.out / name).as_posix()}"],
                          out_file=f"metric-data-{n // METRICS_PER_CALL:03d}.json")

    def inventory(self):
        uri = self.args.inventory_manifest
        target = self.out / "inventory"
        target.mkdir(parents=True, exist_ok=True)
        self.paid["s3_get_requests"] += 1
        if not self.aws_call("s3", "cp", [uri, str(target / "manifest.json"), "--only-show-errors"]):
            return
        manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
        bucket = str(manifest.get("destinationBucket", "")).split(":::")[-1]
        keys = [f.get("key") for f in manifest.get("files") or [] if f.get("key")]
        if len(keys) > self.args.max_inventory_files:
            self.warnings.append({"api": "s3 cp", "code": "inventory-files-over-cap",
                                  "message": f"{len(keys)} files > cap {self.args.max_inventory_files}; data not downloaded"})
            return
        for key in keys:
            self.paid["s3_get_requests"] += 1
            self.aws_call("s3", "cp", [f"s3://{bucket}/{key}", str(target / Path(key).name), "--only-show-errors"])
        self.files.append("inventory/manifest.json")
        self.counts["inventory_files"] = len(keys)

    # ------------------------------------------------------------ summary
    def summary(self, status):
        cost = {k: usd(self.paid[p] * RATES[r]["usd"]) for k, p, r in (
            ("cost_explorer", "cost_explorer_requests", "cost_explorer_request"),
            ("get_metric_data", "get_metric_data_metrics", "get_metric_data_metric"),
            ("s3_get", "s3_get_requests", "s3_get_request"),
            ("glue_catalog_before_free_tier", "glue_catalog_requests", "glue_catalog_request"))}
        cost["total_excluding_glue_free_tier"] = usd(sum(Decimal(v) for k, v in cost.items() if not k.startswith("glue")))
        return {"status": status, "period": {"start": self.args.start.isoformat(), "end_exclusive": self.args.end.isoformat()},
                "services": list(self.args.services), "profile": self.args.profile, "calls": dict(sorted(self.calls.items())),
                "paid_units": self.paid, "estimated_usd": cost,
                "rates": {k: {**v, "usd": format(v["usd"], "f")} for k, v in RATES.items()},
                "resource_counts": self.counts, "files": sorted(self.files), "warnings": self.warnings,
                "note": "Estimated from published rates; check the bill for the actual charge."}


def _parse_time(x):
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return datetime.fromtimestamp(x, timezone.utc)
    if isinstance(x, str):
        try:
            d = datetime.fromisoformat(x.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def dry_run_plan(args):
    s = set(args.services)
    free = []
    if "firehose" in s:
        free += ["firehose list-delivery-streams", "firehose describe-delivery-stream (per stream)"]
    if "athena" in s:
        free += ["athena list-work-groups", f"athena list-query-executions (per work group, max {args.max_athena_queries})",
                 "athena batch-get-query-execution (per 50 IDs)"]
        free += ["glue get-tables (per database, metered: first 1M catalog requests/month free)"] if args.glue_databases else []
    if "sagemaker" in s:
        free += ["sagemaker list-notebook-instances", "sagemaker describe-notebook-instance (per notebook)",
                 "sagemaker list-endpoints", "sagemaker describe-endpoint / describe-endpoint-config (per endpoint)"]
    paid = []
    worst = Decimal(0)
    if "cost" in s:
        c = args.max_ce_requests * RATES["cost_explorer_request"]["usd"]
        worst += c
        paid.append({"api": "ce get-cost-and-usage", "max_requests": args.max_ce_requests, "max_usd": usd(c)})
    if "cloudwatch" in s:
        c = args.max_metrics * RATES["get_metric_data_metric"]["usd"]
        worst += c
        paid.append({"api": "cloudwatch get-metric-data", "max_metrics": args.max_metrics, "max_usd": usd(c),
                     "metrics": "1 per Firehose stream + 2 per endpoint variant, counted after the free phase"})
    if "s3-inventory" in s:
        c = (1 + args.max_inventory_files) * RATES["s3_get_request"]["usd"]
        worst += c
        paid.append({"api": "s3 cp (Inventory manifest + data files)", "max_get_requests": 1 + args.max_inventory_files,
                     "max_usd": usd(c), "not_included": "data transfer out to this PC (rate not in the snapshot)"})
    return {"status": "dry-run", "aws_calls_made": 0, "profile": args.profile,
            "period": {"start": args.start.isoformat(), "end_exclusive": args.end.isoformat()},
            "free_phase": free, "paid_phase": paid, "worst_case_usd": usd(worst),
            "paid_calls_need": "--yes", "rates": {k: {**v, "usd": format(v["usd"], "f")} for k, v in RATES.items()}}


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, required=True, help="output folder outside the repository (new or empty)")
    p.add_argument("--start", type=date.fromisoformat, help="UTC start date (inclusive)")
    p.add_argument("--end", type=date.fromisoformat, help="UTC end date (exclusive), default today")
    p.add_argument("--days", type=int, help="instead of --start: number of days before --end")
    p.add_argument("--services", default=",".join(DEFAULT_SERVICES))
    p.add_argument("--profile", default="cel-readonly")
    p.add_argument("--region", default="ap-northeast-2")
    p.add_argument("--glue-databases", nargs="+")
    p.add_argument("--inventory-manifest", help="s3://... manifest.json of an S3 Inventory report")
    p.add_argument("--max-ce-requests", type=int, default=3)
    p.add_argument("--max-metrics", type=int, default=500)
    p.add_argument("--max-athena-queries", type=int, default=5000)
    p.add_argument("--max-inventory-files", type=int, default=20)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true", help="allow the paid phase (within the caps)")
    p.add_argument("--aws-cmd", help=argparse.SUPPRESS)  # tests: replace the aws executable
    args = p.parse_args(argv)
    args.end = args.end or datetime.now(timezone.utc).date()
    if args.start is None:
        if not args.days:
            p.error("give --start or --days")
        args.start = args.end - timedelta(days=args.days)
    if args.start >= args.end:
        p.error("--start must be before --end")
    args.services = tuple(x.strip() for x in args.services.split(",") if x.strip())
    if not set(args.services) <= set(SERVICES):
        p.error(f"--services must be among {', '.join(SERVICES)}")
    if "s3-inventory" in args.services and not args.inventory_manifest:
        p.error("s3-inventory needs --inventory-manifest")
    out = args.out.resolve()
    try:
        out.relative_to(REPO)
        p.error("--out must be outside the repository")
    except ValueError:
        pass
    if not args.dry_run and out.exists() and any(out.iterdir()):
        p.error("--out must be a new or empty folder")
    args.out = out
    return args


def main(argv=None):
    args = parse_args(argv)
    if args.dry_run:
        print(json.dumps(dry_run_plan(args), indent=2))
        return 0
    args.out.mkdir(parents=True, exist_ok=True)
    c = Collector(args)
    s = set(args.services)
    for name in ("firehose", "athena", "sagemaker"):
        if name in s:
            getattr(c, name)()
    plan = c.paid_plan()
    status = "complete"
    print(json.dumps({"paid_plan": plan}, indent=2), file=sys.stderr)
    if plan["get_metric_data_metrics"] > args.max_metrics:
        status = "stopped-cap-exceeded"
        c.warnings.append({"api": "cloudwatch get-metric-data", "code": "cap-exceeded",
                           "message": f"{plan['get_metric_data_metrics']} metrics > --max-metrics {args.max_metrics}"})
    elif any((plan["cost_explorer_requests_max"], plan["get_metric_data_metrics"], plan["s3_inventory"])) and not args.yes:
        status = "stopped-before-paid-phase"
    else:
        if "cost" in s:
            c.cost()
        if "cloudwatch" in s and plan["get_metric_data_metrics"]:
            c.cloudwatch()
        if plan["s3_inventory"]:
            c.inventory()
    (args.out / "requests.log").write_text("\n".join(c.log) + "\n", encoding="utf-8")
    summary = c.summary(status)
    c.save("collect-summary.json", summary)
    print(json.dumps({k: summary[k] for k in ("status", "calls", "paid_units", "estimated_usd", "resource_counts")}, indent=2))
    return 1 if status == "stopped-cap-exceeded" else 0


if __name__ == "__main__":
    sys.exit(main())
