"""Build references/aws-price-list-apn2-2026-11-15.json from downloaded Seoul offer files.

Usage: py -3 -I extract.py <offer_dir> <out_path>
Selection = exact usagetype list (plus attribute filters noted per offer).
"""
import json, re, sys
from pathlib import Path

SRC = Path(sys.argv[1]); OUT = Path(sys.argv[2])

PG = lambda a: a.get("databaseEngine") == "PostgreSQL"
SEL = {
    "AWSIoT": (r"APN2-(ActionsExecuted|ConnectionMinutes|Messages|RegistryAndShadowOperations|RulesTriggered)", None,
               "all Seoul usagetypes in offer"),
    "AmazonKinesisFirehose": (r"APN2-(BilledBytes|DFCBilledBytes|DPBytesDelivered|DirectPUT-no-rounding-BilledBytes|MetadataProcessingDuration|S3DeliveryObjectCount)", None,
                              "same usagetypes as 2026-11-13 snapshot"),
    "AmazonAthena": (r"APN2-DataScannedInTB", None, "SQL query scan"),
    "AmazonS3": (r"APN2-(Requests-Tier1|Requests-Tier2|TimedStorage-ByteHrs|TimedStorage-SIA-ByteHrs|TimedStorage-GIR-ByteHrs|TimedStorage-GlacierByteHrs)", None,
                 "requests, Standard / Standard-IA / Glacier IR / Glacier Flexible storage"),
    "AmazonBedrockFoundationModels": (r"APN2-MP:APN2_.*(InputTokenCount|OutputTokenCount|Cache\w*InputTokenCount|input_tokens|output_tokens|cache_\w*tokens)\w*_(Global|global_standard)(_Batch)?-Units",
                                      lambda a: a.get("model") in ("Claude Haiku 4.5", "Claude Sonnet 4.5", "Claude Haiku 5.5", "Claude Sonnet 5.5"),
                                      "on-demand/batch token usagetypes (Global) for 4 Claude models; provisioned throughput excluded"),
    "AmazonBedrock": (r"APN2-(Nova(Lite|Micro)-(input-tokens|output-tokens|cache-read-input-token-count)(-batch)?|Guardrail-\w+)", None,
                      "Nova Lite/Micro tokens + Guardrails policy text units"),
    "AmazonES": (r"APN2-(IndexingOCU|SearchOCU|IngestionOCU|ESInstance:(m7g\.large|t3\.small)|ES:GP3-Storage|ES:Managed-Storage)", None,
                 "Serverless OCU, two managed-domain instance types, gp3 and managed storage"),
    "AmazonElastiCache": (r"APN2-(NodeUsage:cache\.(t4g\.micro|t4g\.small|m7g\.large)|CachedData:(Valkey|Redis)|ElastiCacheProcessingUnits:(Valkey|Redis)|BackupUsage:(Valkey|Redis))", None,
                          "three node types (all engines), serverless storage and ECPU, backup"),
    "AmazonApiGateway": (r"APN2-(ApiGatewayHttpRequest|ApiGatewayRequest|ApiGatewayMessage|ApiGatewayMinute)", None,
                         "HTTP API, REST API, WebSocket messages and connection minutes"),
    "AWSLambda": (r"APN2-(Lambda-GB-Second(-ARM)?|Request(-ARM)?|Lambda-Event-Poller-Unit-Hour|Lambda-SQS-Event-Poller-Unit-Hour)", None,
                  "on-demand compute, requests, provisioned-mode pollers"),
    "AmazonRDS": (r"APN2-(InstanceUsage|Multi-AZUsage):db\.(t4g\.micro|t4g\.medium|m7g\.large)|APN2-RDS:(GP3-Storage|Multi-AZ-GP3-Storage|ChargedBackupUsage)",
                  lambda a: PG(a), "PostgreSQL only; three instance classes, gp3, backup"),
    "AmazonVPC": (r"APN2-(VpcEndpoint-Hours|VpcEndpoint-Bytes|PublicIPv4:InUseAddress|PublicIPv4:IdleAddress)", None,
                  "interface endpoint hours/bytes, public IPv4"),
    "AmazonEC2": (r"APN2-(NatGateway-Hours|NatGateway-Bytes|BoxUsage:(m7g\.large|m5\.large|m7i\.large|c7g\.large|t4g\.medium)|EBS:VolumeUsage\.gp3|DataTransfer-Regional-Bytes)",
                  lambda a: ("BoxUsage" not in a.get("usagetype", "")) or (a.get("operatingSystem") == "Linux" and a.get("tenancy") == "Shared" and a.get("preInstalledSw") == "NA" and a.get("capacitystatus") == "Used"),
                  "zonal NAT gateway, Linux shared on-demand instances, gp3, inter-AZ transfer"),
    "AmazonEKS": (r"APN2-(AmazonEKS-Hours:(perCluster|extendedSupport)|Fargate-(vCPU-Hours:perCPU|GB-Hours|EphemeralStorage-GB-Hours|ARM-vCPU-Hours:perCPU|ARM-GB-Hours))", None,
                  "cluster hours (standard/extended), Fargate"),
    "AmazonECS": (r"APN2-Fargate-(vCPU-Hours:perCPU|GB-Hours|EphemeralStorage-GB-Hours|ARM-vCPU-Hours:perCPU|ARM-GB-Hours)", None, "Fargate"),
    "AmazonECR": (r"APN2-TimedStorage-(ByteHrs|ArchiveByteHrs)", None, "image storage"),
    "AmazonCloudWatch": (r"APN2-(CW:MetricMonitorUsage|CW:GMD-Metrics|CW:AlarmMonitorUsage|TimedStorage-ByteHrs|DataProcessing-Bytes|DataProcessingIA-Bytes|VendedLog-Bytes)", None,
                         "custom metrics tiers, GetMetricData, alarms, log ingest (Standard/IA/vended), log storage"),
    "AWSGlue": (r"APN2-(ETL-DPU-Hour(-Gen2)?|ETL-Flex-DPU-Hour(-Gen2)?|Crawler-DPU-Hour|Catalog-Storage|Catalog-Request)", None,
                "ETL (incl. Gen2/Flex), crawler, catalog"),
}

offers = {}
for name, (pat, pred, cond) in SEL.items():
    d = json.loads((SRC / f"{name}.json").read_text(encoding="utf-8"))
    rx = re.compile(pat + r"$")
    rows, seen = [], set()
    for sku, p in d["products"].items():
        a = p.get("attributes", {})
        ut = a.get("usagetype", "")
        if not rx.match(ut) or (pred and not pred(a)):
            continue
        for term in d["terms"].get("OnDemand", {}).get(sku, {}).values():
            for pd in term["priceDimensions"].values():
                r = {"usagetype": ut, "operation": a.get("operation", ""), "description": pd["description"],
                     "unit": pd["unit"], "usd": pd["pricePerUnit"].get("USD"),
                     "begin": pd.get("beginRange", ""), "end": pd.get("endRange", "")}
                for k in ("model", "cacheEngine", "instanceType", "databaseEngine", "deploymentOption"):
                    if a.get(k):
                        r[k] = a[k]
                key = json.dumps(r, sort_keys=True)
                if key not in seen:
                    seen.add(key); rows.append(r)
    rows.sort(key=lambda r: (r.get("model", ""), r["usagetype"], r.get("cacheEngine", ""), r["operation"], float(r["begin"] or 0), r["description"]))
    offers[name] = {"publicationDate": d["publicationDate"], "selection": cond, "rows": rows}
    print(name, len(rows), file=sys.stderr)

MISSING = [
    {"item": "Internet data transfer out (Seoul)", "reason": "not in AmazonEC2/AmazonVPC offers checked; lives in AWSDataTransfer offer, not downloaded"},
    {"item": "Glue Python Shell job DPU-hour and minimum billed duration", "reason": "no Python-Shell usagetype in AWSGlue offer; whether ETL-DPU-Hour applies and the minimum duration were not confirmed"},
    {"item": "Bedrock Knowledge Base managed index storage (5 USD per GB of source data per month on pricing page)", "reason": "no matching usagetype found in AmazonBedrock offer; pricing page only partly readable"},
    {"item": "OpenSearch Serverless NextGen OCU rates", "reason": "offer does not label NextGen separately; IndexingOCU/SearchOCU rows used for both"},
    {"item": "API Gateway HTTP API 512 KB metering increment", "reason": "appears only in pricing-page example, not in offer"},
]

out = {
    "region": "ap-northeast-2",
    "retrieved": "2026-11-15",
    "source": "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/{offer}/current/ap-northeast-2/index.json",
    "note": ("On-Demand public rates only. No free tier, discounts, tax. Extracted verbatim from AWS Price List Bulk API on 2026-11-15. "
             "Each offer lists its publicationDate and the selection condition; rows are matched by exact usagetype pattern. "
             "Rates not found are in 'missing' and must not be estimated. The 2026-11-13 snapshot is kept unchanged."),
    "missing": MISSING,
    "offers": offers,
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
