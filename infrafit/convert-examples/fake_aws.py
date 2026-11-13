"""Fake aws CLI for infrafit/test_collect.py. Serves synthetic responses from convert-examples/.

Every call is appended to the file named by FAKE_AWS_LOG. FAKE_AWS_FAIL=<service op>
makes that operation fail with an AccessDenied-style message that contains an ARN and
a placeholder account ID. FAKE_AWS_EXTRA_STREAMS=<n> adds n more delivery streams.
Never contacts AWS.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import sys

EX = Path(__file__).resolve().parent


def load(name):
    return json.loads((EX / name).read_text(encoding="utf-8"))


def opt(argv, name, many=False):
    if name not in argv:
        return None
    i = argv.index(name) + 1
    if not many:
        return argv[i]
    out = []
    while i < len(argv) and not argv[i].startswith("--"):
        out.append(argv[i])
        i += 1
    return out


def metric_values(q, start, end):
    days = int((end - start).total_seconds() // 86400)
    stamps = [(start + timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%SZ") for d in range(days)]
    m = q["MetricStat"]["Metric"]["MetricName"]
    if m == "IncomingBytes":
        vals = [172800000] * days
    elif m == "Invocations":
        vals = [100000 // days] * days
        vals[0] += 100000 - sum(vals)
    else:
        vals = [200000] * days
    return {"Id": q["Id"], "Label": m, "StatusCode": "Complete", "Timestamps": stamps, "Values": vals}


def main(argv):
    log = os.environ.get("FAKE_AWS_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps(argv) + "\n")
    service, op = argv[0], argv[1]
    if os.environ.get("FAKE_AWS_FAIL") == f"{service} {op}":
        sys.stderr.write("An error occurred (AccessDeniedException): User: arn:aws:iam::123456789012:user/cel-readonly "
                         "is not authorized to perform this action\n")
        return 254
    extra = int(os.environ.get("FAKE_AWS_EXTRA_STREAMS", "0"))
    if (service, op) == ("firehose", "list-delivery-streams"):
        doc = {"DeliveryStreamNames": ["sensor-raw-60s"] + [f"extra-{i}" for i in range(extra)], "HasMoreDeliveryStreams": False}
    elif (service, op) == ("firehose", "describe-delivery-stream"):
        doc = load("firehose-sensor-raw-60s.json")
        doc["DeliveryStreamDescription"]["DeliveryStreamName"] = opt(argv, "--delivery-stream-name")
    elif (service, op) == ("athena", "list-work-groups"):
        doc = {"WorkGroups": [{"Name": "primary", "State": "ENABLED"}]}
    elif (service, op) == ("athena", "list-query-executions"):
        ids = [q["QueryExecutionId"] for q in load("athena-queries.json")["QueryExecutions"]]
        doc = {"QueryExecutionIds": ids[: int(opt(argv, "--max-items") or len(ids))]}
    elif (service, op) == ("athena", "batch-get-query-execution"):
        wanted = set(opt(argv, "--query-execution-ids", many=True))
        if len(wanted) > 50:
            sys.stderr.write("InvalidRequestException: too many IDs\n")
            return 254
        doc = {"QueryExecutions": [q for q in load("athena-queries.json")["QueryExecutions"] if q["QueryExecutionId"] in wanted],
               "UnprocessedQueryExecutionIds": []}
    elif (service, op) == ("glue", "get-tables"):
        doc = {"TableList": [load(f"glue-{n}.json")["Table"] for n in ("sensor_csv_dashboard", "sensor_parquet_daily")]}
    elif (service, op) == ("sagemaker", "list-notebook-instances"):
        doc = {"NotebookInstances": [{"NotebookInstanceName": "gpu-always-on", "InstanceType": "ml.g4dn.xlarge"}]}
    elif (service, op) == ("sagemaker", "describe-notebook-instance"):
        doc = load("notebook-gpu-always-on.json")
    elif (service, op) == ("sagemaker", "list-endpoints"):
        doc = {"Endpoints": [{"EndpointName": "anomaly-scorer", "EndpointStatus": "InService"}]}
    elif (service, op) == ("sagemaker", "describe-endpoint"):
        doc = load("endpoint-anomaly-scorer.json")
    elif (service, op) == ("sagemaker", "describe-endpoint-config"):
        doc = load("endpoint-config-anomaly-scorer.json")
    elif (service, op) == ("ce", "get-cost-and-usage"):
        doc = load("ce-page2.json" if opt(argv, "--next-page-token") else "ce-page1.json")
    elif (service, op) == ("cloudwatch", "get-metric-data"):
        path = opt(argv, "--cli-input-json")[len("file://"):]
        req = json.loads(Path(path).read_text(encoding="utf-8"))
        start, end = (datetime.fromisoformat(req[k].replace("Z", "+00:00")) for k in ("StartTime", "EndTime"))
        doc = {"Messages": [], "MetricDataResults": [metric_values(q, start, end) for q in req["MetricDataQueries"]]}
    elif (service, op) == ("s3", "cp"):
        src, dst = argv[2], Path(argv[3])
        shutil.copy(EX / "inventory" / ("manifest.json" if src.endswith("manifest.json") else Path(src).name), dst)
        return 0
    else:
        sys.stderr.write(f"fake aws: unsupported {service} {op}\n")
        return 2
    sys.stdout.write(json.dumps(doc))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
