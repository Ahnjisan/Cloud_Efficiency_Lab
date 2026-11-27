"""Experiment 040 runner for AWS CloudShell (Python standard library + AWS CLI v2).

Usage (in CloudShell, inside the unzipped bundle):
  python3 run_040.py --haiku <inference-profile-id> --sonnet <inference-profile-id> [--reps 3]
Writes everything under ./out/. Safe to re-run: finished calls are skipped.
Stops at 10 USD estimated cost, two identical consecutive errors, more than 3 throttling retries
on one call, or 110 minutes.
"""
import argparse
import base64
import json
import random
import subprocess
import sys
import time
from pathlib import Path

REGION = "ap-northeast-2"
SEED = 40
BUDGET_STOP = 10.0
TIME_LIMIT_S = 110 * 60
# USD per token (Global cross-Region, 2026-11-15 Seoul snapshot) and per Textract TABLES page (Seoul offer 2026-11-18)
RATES = {"haiku": (1.0e-6, 5.0e-6), "sonnet": (3.0e-6, 15.0e-6)}  # "sonnet" ran as Claude Sonnet 4.6 (4.5 Legacy, 5/5.5 unavailable; see README)
TEXTRACT_PAGE = 0.015

SYSTEM = (
    "너는 측정 기록지를 JSON으로 옮기는 도구다. 적힌 숫자를 고치거나 계산하거나 반올림하지 말고 보이는 그대로 "
    "문자열로 옮긴다(부호, 소수점, 끝자리 0 포함). 줄을 그어 고친 값은 고친 뒤의 값만 쓴다. 읽을 수 없는 값은 null. "
    "출력은 JSON 하나만, 설명 없이. 스키마: {\"drawing_no\": string|null, \"items\": [{\"spec_item\": string, "
    "\"nominal\": string|null, \"tol_plus\": string|null, \"tol_minus\": string|null, \"measured\": [string], "
    "\"deviation\": string|null, \"judgment\": string|null}]}. measured에는 측정값 칸(X1, X2, X3 등)을 순서대로 모두 넣는다. "
    "공차가 한 칸에 '+a / -b'로 적혀 있으면 tol_plus=+a, tol_minus=-b로 나눈다."
)
ASK = {
    "P1": "아래는 측정 기록지 사진을 OCR한 결과다. 이 내용만 보고 스키마대로 JSON을 만들어라.\n\n",
    "P2": "첨부한 측정 기록지 사진을 보고 스키마대로 JSON을 만들어라.",
    "P3": "첨부한 측정 기록지 사진과, 같은 사진의 OCR 결과(참고용, 틀릴 수 있음)를 함께 보고 스키마대로 JSON을 만들어라. "
          "OCR과 사진이 다르면 사진을 따른다.\n\n",
}


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with open("out/run.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def aws(args, payload):
    req = Path("out/_req.json")
    req.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    t0 = time.time()
    p = subprocess.run(["aws", *args, "--region", REGION, "--cli-input-json", f"file://{req}", "--output", "json"],
                       capture_output=True, text=True)
    ms = int((time.time() - t0) * 1000)
    req.unlink()
    return p.returncode, p.stdout, p.stderr.strip(), ms


def ocr_text(resp):
    blocks = {b["Id"]: b for b in resp["Blocks"]}
    words = lambda b: " ".join(blocks[c]["Text"] for r in b.get("Relationships", []) if r["Type"] == "CHILD"
                               for c in r["Ids"] if blocks[c]["BlockType"] == "WORD")
    lines = [b["Text"] for b in resp["Blocks"] if b["BlockType"] == "LINE"]
    out = ["## LINES"] + lines
    for t_i, t in enumerate(b for b in resp["Blocks"] if b["BlockType"] == "TABLE"):
        cells = [blocks[c] for r in t.get("Relationships", []) if r["Type"] == "CHILD" for c in r["Ids"] if blocks[c]["BlockType"] == "CELL"]
        grid = {}
        for c in cells:
            grid[(c["RowIndex"], c["ColumnIndex"])] = words(c)
        rows = max(r for r, _ in grid) if grid else 0
        cols = max(c for _, c in grid) if grid else 0
        out.append(f"## TABLE {t_i + 1}")
        out += ["| " + " | ".join(grid.get((r, c), "") for c in range(1, cols + 1)) + " |" for r in range(1, rows + 1)]
    return "\n".join(out)


class Stop(Exception):
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--haiku", required=True)
    ap.add_argument("--sonnet", required=True)
    ap.add_argument("--reps", type=int, default=3)
    a = ap.parse_args()
    out = Path("out"); out.mkdir(exist_ok=True)
    sheets = sorted(Path("sheets").glob("S*.png"))
    order = sheets[:]
    random.Random(SEED).shuffle(order)
    state = {"cost": 0.0, "last_err": None, "t0": time.time(), "calls": 0, "throttles": 0}
    costfile = out / "cost.json"
    if costfile.exists():
        state["cost"] = json.loads(costfile.read_text())["cost"]

    def charge(usd):
        state["cost"] += usd
        costfile.write_text(json.dumps({"cost": state["cost"]}))
        if state["cost"] >= BUDGET_STOP:
            raise Stop(f"budget {state['cost']:.4f} >= {BUDGET_STOP}")
        if time.time() - state["t0"] > TIME_LIMIT_S:
            raise Stop("time limit")

    def call(kind, payload, dest):
        for attempt in range(4):
            rc, so, se, ms = aws(kind, payload)
            if rc == 0:
                state["last_err"] = None
                return json.loads(so), ms
            if "Throttling" in se or "TooManyRequests" in se or "ServiceUnavailable" in se:
                state["throttles"] += 1
                time.sleep(2 ** (attempt + 1))
                continue
            err = se.split(":")[0][:120]
            (dest.parent / (dest.stem + ".error.txt")).write_text(se[-2000:], encoding="utf-8")
            if err == state["last_err"]:
                raise Stop(f"same error twice: {err}")
            state["last_err"] = err
            return None, ms
        raise Stop("throttling retries exceeded on one call")

    try:
        tdir = out / "textract"; tdir.mkdir(exist_ok=True)
        for s in order:
            dest = tdir / f"{s.stem}.json"
            if dest.exists():
                continue
            b64 = base64.b64encode(s.read_bytes()).decode()
            resp, ms = call(["textract", "analyze-document"], {"Document": {"Bytes": b64}, "FeatureTypes": ["TABLES"]}, dest)
            if resp is None:
                continue
            pages = resp.get("DocumentMetadata", {}).get("Pages", 1)
            dest.write_text(json.dumps({"wall_ms": ms, "pages": pages, "response": resp}, ensure_ascii=False), encoding="utf-8")
            charge(pages * TEXTRACT_PAGE)
            log(f"textract {s.stem} pages={pages} {ms}ms cost={state['cost']:.4f}")
        for model in ("haiku", "sonnet"):
            mid = getattr(a, model)
            for rep in range(1, a.reps + 1):
                for i, s in enumerate(order):
                    approaches = ["P1", "P2", "P3"]
                    k = (i + rep) % 3
                    approaches = approaches[k:] + approaches[:k]
                    for ap_name in approaches:
                        dest = out / model / ap_name / f"r{rep}" / f"{s.stem}.json"
                        if dest.exists():
                            continue
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        tx = tdir / f"{s.stem}.json"
                        content = []
                        if ap_name in ("P2", "P3"):
                            content.append({"image": {"format": "png", "source": {"bytes": base64.b64encode(s.read_bytes()).decode()}}})
                        text = ASK[ap_name]
                        if ap_name in ("P1", "P3"):
                            if not tx.exists():
                                log(f"skip {model} {ap_name} {s.stem}: no textract result")
                                continue
                            text += ocr_text(json.loads(tx.read_text(encoding="utf-8"))["response"])
                        content.append({"text": text})
                        payload = {"modelId": mid, "system": [{"text": SYSTEM}], "messages": [{"role": "user", "content": content}],
                                   "inferenceConfig": {"temperature": 0, "maxTokens": 3000}}
                        resp, ms = call(["bedrock-runtime", "converse"], payload, dest)
                        state["calls"] += 1
                        if resp is None:
                            continue
                        u = resp.get("usage", {})
                        rin, rout = RATES[model]
                        usd = (u.get("inputTokens", 0) + u.get("cacheReadInputTokens", 0) + u.get("cacheWriteInputTokens", 0)) * rin + u.get("outputTokens", 0) * rout
                        dest.write_text(json.dumps({"model": model, "model_id": mid, "approach": ap_name, "rep": rep, "sheet": s.stem,
                                                    "wall_ms": ms, "usd_estimate": usd, "response": resp}, ensure_ascii=False), encoding="utf-8")
                        charge(usd)
                        log(f"{model} r{rep} {ap_name} {s.stem} in={u.get('inputTokens')} out={u.get('outputTokens')} {ms}ms cost={state['cost']:.4f}")
                        time.sleep(0.5)
        log(f"DONE calls={state['calls']} throttles={state['throttles']} cost={state['cost']:.4f}")
    except Stop as e:
        log(f"STOP {e} calls={state['calls']} throttles={state['throttles']} cost={state['cost']:.4f}")
    except KeyboardInterrupt:
        log("INTERRUPTED")


if __name__ == "__main__":
    main()
