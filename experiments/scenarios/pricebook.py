"""Read Seoul on-demand rates from the 2026-11-15 Price List snapshot as Decimal.

Experiments 026-036 read every rate through this module, so all amounts trace
back to one dated snapshot. A rate that is not in the snapshot raises KeyError;
callers must record it as missing instead of guessing.
"""
from decimal import Decimal
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "references" / "aws-price-list-apn2-2026-11-15.json"
HOURS_PER_MONTH = Decimal(730)
INF = Decimal("Infinity")


def _num(text):
    return INF if text in ("Inf", "", None) else Decimal(str(text))


class PriceBook:
    def __init__(self, path=SNAPSHOT):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self.used = {}

    def publication(self, offer):
        return self.data["offers"][offer]["publicationDate"]

    def rows(self, offer, usagetype, **attrs):
        return [r for r in self.data["offers"][offer]["rows"]
                if r["usagetype"] == usagetype and all(r.get(k) == v for k, v in attrs.items())]

    def rate(self, offer, usagetype, begin=0, **attrs):
        """Unit price of the tier that starts at `begin`. Duplicate rows must agree."""
        hits = {Decimal(r["usd"]) for r in self.rows(offer, usagetype, **attrs) if _num(r["begin"]) == Decimal(begin)}
        if not hits:
            raise KeyError(f"rate not in snapshot: {offer} {usagetype} {attrs} begin={begin}")
        if len(hits) > 1:
            raise ValueError(f"ambiguous rate: {offer} {usagetype} {attrs}: {sorted(hits)}")
        value = hits.pop()
        self.used[f"{offer}|{usagetype}|{begin}|{json.dumps(attrs, sort_keys=True)}"] = str(value)
        return value

    def tiers(self, offer, usagetype, **attrs):
        seen = {}
        for r in self.rows(offer, usagetype, **attrs):
            key = (_num(r["begin"]), _num(r["end"]))
            if key in seen and seen[key] != Decimal(r["usd"]):
                raise ValueError(f"ambiguous tier {offer} {usagetype} {key}")
            seen[key] = Decimal(r["usd"])
        if not seen:
            raise KeyError(f"rate not in snapshot: {offer} {usagetype} {attrs}")
        return sorted((b, e, p) for (b, e), p in seen.items())

    def tiered(self, offer, usagetype, quantity, **attrs):
        """Cost of `quantity` units across the tiers (tier bounds are in the same unit)."""
        q = Decimal(quantity)
        total = Decimal(0)
        for begin, end, price in self.tiers(offer, usagetype, **attrs):
            if q > begin:
                total += (min(q, end) - begin) * price
        self.used[f"{offer}|{usagetype}|tiered|{json.dumps(attrs, sort_keys=True)}"] = "tiers"
        return total


def money(x, places="0.01"):
    return str(Decimal(x).quantize(Decimal(places)))


def load_scenario(name):
    return json.loads((Path(__file__).resolve().parent / f"{name}.json").read_text(encoding="utf-8"))


def emit(obj):
    """Print JSON as UTF-8 regardless of the console code page (Windows redirection)."""
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(obj, indent=1, ensure_ascii=False))
