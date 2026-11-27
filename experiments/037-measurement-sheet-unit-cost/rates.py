"""Shared rates and workload assumptions for experiments 037-041 (Fac:Hub measurement-sheet pipeline).

Snapshot rates come from experiments/scenarios/pricebook.py (2026-11-15 Seoul snapshot);
rates missing from the snapshot come from rates_manual.json next to this file.
"""
from decimal import Decimal as D
from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scenarios"))
from pricebook import PriceBook, emit, money  # noqa: E402,F401

MANUAL = json.loads((HERE / "rates_manual.json").read_text(encoding="utf-8"))
M = D(10 ** 6)
GB = D(1024 ** 3)
HOURS_30D = D(720)
WORKDAYS = 22

# Assumed workload tiers (not measured).
VOLUMES = {
    "small": {"sheets_per_day": 20, "pages_per_photo_sheet": D("1.0")},
    "medium": {"sheets_per_day": 100, "pages_per_photo_sheet": D("1.3")},
    "large": {"sheets_per_day": 500, "pages_per_photo_sheet": D("1.3")},
}
TOKENS = {"small": (1500, 300), "medium": (3000, 600), "large": (5000, 1000)}
TEXTRACT = {"detect": "DetectDocumentText", "tables": "AnalyzeDocument_Tables", "tables_forms": "AnalyzeDocument_TablesForms"}
MODELS = ("Claude Haiku 4.5", "Claude Sonnet 4.5")
PHOTO_BYTES = 2 * 1024 * 1024
CSV_BYTES = 50 * 1024


class Rates:
    def __init__(self):
        self.pb = PriceBook()
        t = MANUAL["textract"]
        self.textract = {k: D(t[v]["usd_per_page"]) for k, v in TEXTRACT.items()}
        self.sqs = D(MANUAL["sqs"]["standard_usd_per_request"]["usd"])
        self.s3_put = self.pb.rate("AmazonS3", "APN2-Requests-Tier1")
        self.s3_get = self.pb.rate("AmazonS3", "APN2-Requests-Tier2")
        self.s3_gb_month = self.pb.rate("AmazonS3", "APN2-TimedStorage-ByteHrs")  # first tier
        self.model = {m: {"in": self.pb.rate("AmazonBedrockFoundationModels", "APN2-MP:APN2_InputTokenCount_Global-Units", model=m) / M,
                          "out": self.pb.rate("AmazonBedrockFoundationModels", "APN2-MP:APN2_OutputTokenCount_Global-Units", model=m) / M,
                          "cache_read": self.pb.rate("AmazonBedrockFoundationModels", "APN2-MP:APN2_CacheReadInputTokenCount_Global-Units", model=m) / M,
                          "cache_write": self.pb.rate("AmazonBedrockFoundationModels", "APN2-MP:APN2_CacheWriteInputTokenCount_Global-Units", model=m) / M}
                      for m in MODELS}

    def bedrock_call(self, model, tin, tout):
        r = self.model[model]
        return D(tin) * r["in"] + D(tout) * r["out"]

    def as_dict(self):
        return {"textract_usd_per_page": {k: str(v) for k, v in self.textract.items()}, "sqs_usd_per_request": str(self.sqs),
                "s3_put": str(self.s3_put), "s3_get": str(self.s3_get), "s3_gb_month": str(self.s3_gb_month),
                "bedrock_usd_per_token": {m: {k: str(v) for k, v in r.items()} for m, r in self.model.items()},
                "bedrock_note": "Global cross-Region rows; in-region/geographic rates: 확인 필요"}
