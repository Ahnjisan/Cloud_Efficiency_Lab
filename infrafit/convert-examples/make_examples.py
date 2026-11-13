"""Write synthetic AWS-shaped responses for infrafit/convert.py tests (all values are synthetic).

The responses mirror real API output structure (aws CLI JSON, S3 Inventory CSV,
Converse usage) and are derived from existing InfraFit examples so a converted
item must reproduce the original decision:
  daily_costs 'AWS IoT' / 'Amazon Bedrock' (021), firehose 'sensor-raw-60s' (017),
  athena 'sensor_csv_dashboard' / 'sensor_parquet_daily' (018),
  notebook 'gpu-always-on' (022), endpoint 'anomaly-scorer', bedrock 'agent-planner' (020) and 'cached-dense'.
Placeholder account 123456789012 and bucket names are deliberately included so tests
can check they never reach the converted output.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import gzip
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INFRAFIT = HERE.parent
ARN = "arn:aws:iam::123456789012:role/example-firehose-delivery"
BUCKET = "example-sensor-bucket"
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def load(name):
    return json.loads((INFRAFIT / name).read_text(encoding="utf-8"))


def write(name, doc):
    path = HERE / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    ops_src, wl_src = load("workloads-ops.json"), load("workloads.json")
    find = lambda section, key, name: next(x for x in ops_src[section] if (x.get(key) if key != "table" else x["table"]["Name"]) == name)

    # ---- Cost Explorer: SERVICE x USAGE_TYPE, two pages
    series = {s["service"]: s["ResultsByTime"] for s in ops_src["daily_costs"] if s["service"] in ("AWS IoT", "Amazon Bedrock")}
    days = len(next(iter(series.values())))
    rows = []
    for i in range(days):
        groups = []
        for service, points in series.items():
            amount = Decimal(points[i]["Metrics"]["NetUnblendedCost"]["Amount"])
            for usage, part in (("APN2-UsageA", amount - Decimal("0.01")), ("APN2-UsageB", Decimal("0.01"))):
                groups.append({"Keys": [service, usage], "Metrics": {
                    "NetUnblendedCost": {"Amount": str(part), "Unit": "USD"},
                    "UsageQuantity": {"Amount": "1", "Unit": "N/A"}}})
        p = next(iter(series.values()))[i]
        rows.append({"TimePeriod": p["TimePeriod"], "Total": {}, "Groups": groups, "Estimated": p["Estimated"]})
    defs = [{"Type": "DIMENSION", "Key": "SERVICE"}, {"Type": "DIMENSION", "Key": "USAGE_TYPE"}]
    write("ce-page1.json", {"GroupDefinitions": defs, "ResultsByTime": rows[:30], "NextPageToken": "synthetic-token",
                            "DimensionValueAttributes": []})
    write("ce-page2.json", {"GroupDefinitions": defs, "ResultsByTime": rows[30:], "DimensionValueAttributes": []})

    # ---- Firehose sensor-raw-60s
    fh = find("firehose_buffers", "DeliveryStreamName", "sensor-raw-60s")
    write("firehose-sensor-raw-60s.json", {"DeliveryStreamDescription": {
        "DeliveryStreamName": "sensor-raw-60s",
        "DeliveryStreamARN": "arn:aws:firehose:ap-northeast-2:123456789012:deliverystream/sensor-raw-60s",
        "DeliveryStreamStatus": "ACTIVE", "DeliveryStreamType": "DirectPut",
        "Destinations": [{"DestinationId": "destinationId-000000000001", "ExtendedS3DestinationDescription": {
            "RoleARN": ARN, "BucketARN": f"arn:aws:s3:::{BUCKET}", "Prefix": "raw/",
            "BufferingHints": fh["BufferingHints"], "CompressionFormat": "UNCOMPRESSED",
            "EncryptionConfiguration": {"NoEncryptionConfig": "NoEncryption"},
            "DynamicPartitioningConfiguration": {"Enabled": False}}}],
        "HasMoreDestinations": False}})

    # ---- CloudWatch GetMetricData (request + response)
    nb_ep = find("sagemaker_endpoints", "EndpointName", "anomaly-scorer")
    queries = [
        {"Id": "fh0", "MetricStat": {"Metric": {"Namespace": "AWS/Firehose", "MetricName": "IncomingBytes",
                                                "Dimensions": [{"Name": "DeliveryStreamName", "Value": "sensor-raw-60s"}]},
                                     "Period": 86400, "Stat": "Sum"}},
        {"Id": "ep0", "MetricStat": {"Metric": {"Namespace": "AWS/SageMaker", "MetricName": "Invocations",
                                                "Dimensions": [{"Name": "EndpointName", "Value": "anomaly-scorer"},
                                                               {"Name": "VariantName", "Value": "AllTraffic"}]},
                                     "Period": 86400, "Stat": "Sum"}},
        {"Id": "ep1", "MetricStat": {"Metric": {"Namespace": "AWS/SageMaker", "MetricName": "ModelLatency",
                                                "Dimensions": [{"Name": "EndpointName", "Value": "anomaly-scorer"},
                                                               {"Name": "VariantName", "Value": "AllTraffic"}]},
                                     "Period": 86400, "Stat": "Average"}},
    ]
    write("metric-queries.json", {"StartTime": iso(T0), "EndTime": iso(T0 + timedelta(days=30)),
                                  "MetricDataQueries": queries, "ScanBy": "TimestampDescending"})
    stamps = [iso(T0 + timedelta(days=d)) for d in range(29, -1, -1)]
    inv = [nb_ep["Invocations_sum"] // 30] * 29
    inv.insert(0, nb_ep["Invocations_sum"] - sum(inv))
    write("metric-data.json", {"Messages": [], "MetricDataResults": [
        {"Id": "fh0", "Label": "IncomingBytes", "StatusCode": "Complete", "Timestamps": stamps,
         "Values": [fh["IncomingBytes_daily_sum"]] * 30},
        {"Id": "ep0", "Label": "Invocations", "StatusCode": "Complete", "Timestamps": stamps, "Values": inv},
        {"Id": "ep1", "Label": "ModelLatency", "StatusCode": "Complete", "Timestamps": stamps,
         "Values": [nb_ep["ModelLatency_avg_us"]] * 30}]})

    # ---- S3 Inventory (CSV, no header, schema in manifest)
    lines = []
    day_count, size = fh["s3_objects_daily"]["count"], fh["s3_objects_daily"]["mean_size_bytes"]
    for d in range(2):
        for k in range(day_count):
            t = T0 + timedelta(days=d, seconds=k * 60)
            lines.append([BUCKET, f"raw/{t:%Y/%m/%d/%H}/sensor-raw-60s-{d}-{k:04d}", str(size), iso(t)])
    for k in range(10):  # partial day the inventory ran on
        lines.append([BUCKET, f"raw/2026/01/03/00/partial-{k}", str(size), iso(T0 + timedelta(days=2, seconds=k))])
    csv_table = find("athena_tables", "table", "sensor_csv_dashboard")
    pq_table = find("athena_tables", "table", "sensor_parquet_daily")
    lines.append([BUCKET, "tables/sensor_csv/dt=2026-01-01/data.csv", str(csv_table["table_size_bytes"]), iso(T0)])
    n, mean = pq_table["files"]["count"], pq_table["files"]["mean_size_bytes"]
    sizes = [mean] * (n - 1) + [pq_table["table_size_bytes"] - mean * (n - 1)]
    for i, s in enumerate(sizes):
        lines.append([BUCKET, f"tables/sensor_parquet/dt=2026-01-{i + 1:02d}/part-0.parquet", str(s),
                      iso(T0 + timedelta(days=i))])
    text = "".join(",".join(f'"{v}"' for v in row) + "\n" for row in lines)
    (HERE / "inventory").mkdir(exist_ok=True)
    (HERE / "inventory" / "data-0.csv.gz").write_bytes(gzip.compress(text.encode("utf-8"), mtime=0))
    write("inventory/manifest.json", {
        "sourceBucket": BUCKET, "destinationBucket": "arn:aws:s3:::example-inventory-destination",
        "version": "2016-11-30", "creationTimestamp": str(int((T0 + timedelta(days=2)).timestamp() * 1000)),
        "fileFormat": "CSV", "fileSchema": "Bucket, Key, Size, LastModifiedDate",
        "files": [{"key": f"inventory/{BUCKET}/data/data-0.csv.gz", "size": 1, "MD5checksum": "synthetic"}]})

    # ---- Athena BatchGetQueryExecution + Glue GetTable
    executions = []
    for table, spread_days in ((csv_table, False), (pq_table, True)):
        for i, q in enumerate(table["query_executions"]):
            when = T0 + (timedelta(days=i) if spread_days else timedelta(minutes=i))
            executions.append({"QueryExecutionId": q["QueryExecutionId"], "Query": "SELECT * FROM secret_table WHERE x = 1",
                               "StatementType": q["StatementType"],
                               "ResultConfiguration": {"OutputLocation": f"s3://{BUCKET}/athena-results/"},
                               "QueryExecutionContext": {"Database": "sensors", "Catalog": "AwsDataCatalog"},
                               "Status": {"State": q["Status"]["State"], "SubmissionDateTime": iso(when)},
                               "Statistics": q["Statistics"], "WorkGroup": "primary"})
    write("athena-queries.json", {"QueryExecutions": executions, "UnprocessedQueryExecutionIds": []})
    for table, prefix in ((csv_table, "tables/sensor_csv/"), (pq_table, "tables/sensor_parquet/")):
        sd = dict(table["table"]["StorageDescriptor"], Location=f"s3://{BUCKET}/{prefix}")
        write(f"glue-{table['table']['Name']}.json", {"Table": {
            "Name": table["table"]["Name"], "DatabaseName": "sensors", "CatalogId": "123456789012",
            "StorageDescriptor": sd, "PartitionKeys": table["table"]["PartitionKeys"], "TableType": "EXTERNAL_TABLE"}})

    # ---- SageMaker
    nb = find("sagemaker_notebooks", "NotebookInstanceName", "gpu-always-on")
    write("notebook-gpu-always-on.json", {
        "NotebookInstanceArn": "arn:aws:sagemaker:ap-northeast-2:123456789012:notebook-instance/gpu-always-on",
        "NotebookInstanceName": "gpu-always-on", "NotebookInstanceStatus": "InService",
        "InstanceType": nb["InstanceType"], "RoleArn": ARN, "VolumeSizeInGB": nb["VolumeSizeInGB"]})
    write("endpoint-anomaly-scorer.json", {
        "EndpointName": "anomaly-scorer", "EndpointConfigName": "anomaly-scorer-config",
        "EndpointArn": "arn:aws:sagemaker:ap-northeast-2:123456789012:endpoint/anomaly-scorer",
        "EndpointStatus": "InService",
        "ProductionVariants": [{"VariantName": "AllTraffic", "CurrentInstanceCount": nb_ep["instance_count"],
                                "DesiredInstanceCount": nb_ep["instance_count"]}]})
    write("endpoint-config-anomaly-scorer.json", {
        "EndpointConfigName": "anomaly-scorer-config",
        "ProductionVariants": [{"VariantName": "AllTraffic", "ModelName": "anomaly-model",
                                "InstanceType": nb_ep["InstanceType"], "InitialInstanceCount": nb_ep["instance_count"]}]})

    # ---- Bedrock application usage log (JSON Lines)
    out = []
    for c in wl_src["bedrock_calls"]:
        if not c["run_id"].startswith(("agent-planner", "cached-dense")):
            continue
        usage = {"inputTokens": c["input_tokens"], "outputTokens": c["output_tokens"],
                 "totalTokens": c["input_tokens"] + c["output_tokens"] + c["cache_read_tokens"] + c["cache_write_tokens"],
                 "cacheReadInputTokens": c["cache_read_tokens"], "cacheWriteInputTokens": c["cache_write_tokens"]}
        if c["cache_write_tokens"]:
            usage["cacheDetails"] = [{"inputTokens": c["cache_write_tokens"], "ttl": c["cache_ttl"]}]
        rec = {"timestamp": iso(T0 + timedelta(seconds=c["ts"])), "call_id": c["call_id"], "run_id": c["run_id"],
               "modelId": "global.anthropic.claude-haiku-5-5", "prefix_hash": c["prefix_hash"],
               "prefix_tokens": c["prefix_tokens"], "usage": usage}
        if c["cache_read_tokens"] and not c["cache_write_tokens"]:
            rec["cache_ttl"] = c["cache_ttl"]  # the application knows the TTL it requested
        out.append(json.dumps(rec))
    (HERE / "bedrock-usage.jsonl").write_text("\n".join(out) + "\n", encoding="utf-8")

    # ---- operations file (human input and mappings)
    write("ops-info.json", {
        "note": "Synthetic. In real use this file stays outside the repository.",
        "firehose": {"sensor-raw-60s": {"allowed_freshness_s": fh["allowed_freshness_s"], "s3_prefix": "raw/"}},
        "athena": {
            "queries": {q["QueryExecutionId"]: t["table"]["Name"] for t in (csv_table, pq_table) for q in t["query_executions"]},
            "tables": {"sensor_csv_dashboard": {"s3_prefix": "tables/sensor_csv/",
                                                "conversion_billed_gb_month": csv_table["conversion_billed_gb_month"]},
                       "sensor_parquet_daily": {"s3_prefix": "tables/sensor_parquet/", "compaction": pq_table["compaction"]}}},
        "sagemaker_notebooks": {"gpu-always-on": {k: nb[k] for k in (
            "status_intervals", "activity", "long_running_in_notebook", "proposed_cpu_notebook_hours",
            "training_volume_gb", "s3_artifact_gb")}},
        "sagemaker_endpoints": {"anomaly-scorer": {k: nb_ep[k] for k in (
            "inservice_hours", "always_on_required", "cold_start_acceptable", "serverless_memory_gb")}}})


if __name__ == "__main__":
    main()
