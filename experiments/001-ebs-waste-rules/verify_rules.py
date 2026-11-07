"""Reproduce the two EBS rules on the documented synthetic fixtures."""

from collections import Counter
from typing import NamedTuple


class Volume(NamedTuple):
    id: str
    attached: bool
    owner: str = ""
    evidence: str = "missing"
    purpose: str = "unknown"


class Decision(NamedTuple):
    status: str
    reason: str
    next_owner: str


def connection_rule(volume):
    if volume.attached:
        return Decision("no-alert", "attached", "none")
    return Decision("alert", "detached", "platform-triage")


def evidence_rule(volume):
    if volume.attached:
        return Decision("out-of-scope", "attached", "none")
    owner = volume.owner or "inventory-team"
    if volume.evidence == "conflicting":
        return Decision("hold", "conflicting-records", owner)
    if not volume.owner or volume.evidence != "complete":
        return Decision("hold", "missing-records", owner)
    if volume.purpose == "required":
        return Decision("retain", "operational-or-recovery-need", owner)
    if volume.purpose == "retired-no-dependency":
        return Decision("alert", "retired-without-dependencies", owner)
    return Decision("hold", "purpose-unconfirmed", owner)


# shortcut: fixtures encode reviewed evidence categories; add validation before accepting external data.
VOLUMES = (
    Volume("vol-data", True, "orders"),
    Volume("vol-recovery", False, "operations", "complete", "required"),
    Volume("vol-unknown", False),
    Volume("vol-migrated", False, "orders", "complete", "retired-no-dependency"),
    Volume("vol-temp", False, "batch", "complete", "retired-no-dependency"),
    Volume("vol-stale", True, "batch"),
    Volume("vol-os", True, "operations"),
    Volume("vol-transfer", False, "migration", "conflicting"),
)

# Expected outputs and labels come from the study, separately from the rule inputs.
EXPECTED = {
    "vol-data": (
        Decision("no-alert", "attached", "none"),
        Decision("out-of-scope", "attached", "none"),
        "normal",
    ),
    "vol-recovery": (
        Decision("alert", "detached", "platform-triage"),
        Decision("retain", "operational-or-recovery-need", "operations"),
        "normal",
    ),
    "vol-unknown": (
        Decision("alert", "detached", "platform-triage"),
        Decision("hold", "missing-records", "inventory-team"),
        "unresolved",
    ),
    "vol-migrated": (
        Decision("alert", "detached", "platform-triage"),
        Decision("alert", "retired-without-dependencies", "orders"),
        "waste",
    ),
    "vol-temp": (
        Decision("alert", "detached", "platform-triage"),
        Decision("alert", "retired-without-dependencies", "batch"),
        "waste",
    ),
    "vol-stale": (
        Decision("no-alert", "attached", "none"),
        Decision("out-of-scope", "attached", "none"),
        "waste",
    ),
    "vol-os": (
        Decision("no-alert", "attached", "none"),
        Decision("out-of-scope", "attached", "none"),
        "normal",
    ),
    "vol-transfer": (
        Decision("alert", "detached", "platform-triage"),
        Decision("hold", "conflicting-records", "migration"),
        "unresolved",
    ),
}


def score(decision, label):
    if label == "unresolved":
        return "unresolved"
    if decision.status == "hold":
        return "confirmed-hold"
    if decision.status == "alert":
        return "TP" if label == "waste" else "FP"
    return "FN" if label == "waste" else "TN"


def main():
    metrics = {"A": Counter(), "B": Counter()}
    queues = Counter()
    for volume in VOLUMES:
        first, second, label = EXPECTED[volume.id]
        for rule, result, expected in (
            ("A", connection_rule(volume), first),
            ("B", evidence_rule(volume), second),
        ):
            if result != expected:
                raise AssertionError((volume.id, rule, result, expected))
            metrics[rule][score(result, label)] += 1
            queues[rule] += result.status in ("alert", "hold")
            print(volume.id, rule, *result, sep=" | ")

    expected_metrics = {
        "A": Counter(TP=2, FP=1, FN=1, TN=2, unresolved=2),
        "B": Counter(TP=2, FP=0, FN=1, TN=3, unresolved=2),
    }
    if metrics != expected_metrics or queues != {"A": 5, "B": 4}:
        raise AssertionError((metrics, queues))

    for purpose in ("required", "retired-no-dependency"):
        conflict = Volume("vol-conflict-extra", False, "orders", "conflicting", purpose)
        result = evidence_rule(conflict)
        expected = Decision("hold", "conflicting-records", "orders")
        if result != expected:
            raise AssertionError((conflict, result, expected))
        print(conflict.id, purpose, *result, sep=" | ")

    for rule, counts in metrics.items():
        print(f"{rule}: {dict(counts)}; initial review queue={queues[rule]}")
    print("PASS: 8 baseline volumes and 2 conflict precedence checks")


if __name__ == "__main__":
    main()
