"""Generate 30 synthetic handwritten-style measurement sheets (PNG) and their answer key.

Not real handwriting: values are drawn with Windows handwriting-style fonts (Ink Free, Segoe Print,
Segoe Script) with per-character rotation, offset, size and ink jitter; labels use Malgun Gothic.
Rendering uses headless Edge screenshots (no extra packages). All data is fictional.

Usage: py -3 -B make_sheets.py <out_dir>
"""
from pathlib import Path
import csv
import html
import random
import shutil
import subprocess
import sys
import tempfile

SEED = 40
SHEETS = 30
W, H = 1240, 1754
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
WRITERS = [("Ink Free", 30), ("Segoe Print", 26), ("Segoe Script", 26)]
ITEMS = ["외경 A", "외경 B", "내경", "전장", "폭", "두께", "깊이", "구멍 간격", "평면도", "직각도",
         "단차", "모따기", "홈 폭", "피치", "높이", "편심", "R 치수", "나사 외경", "보스 직경", "리브 두께"]


def num(v, d):
    s = f"{v:.{d}f}"
    return s[1:] if s.startswith("-") and float(s) == 0 else s   # no "-0.0"


def hand(rng, text, writer, faint=False, struck=None):
    """Return HTML spans that imitate handwriting for `text`."""
    font, size = writer
    ink = rng.choice(["#1b2a5c", "#202020", "#14327a", "#2a2a3a"])
    op = rng.uniform(0.38, 0.5) if faint else rng.uniform(0.82, 1.0)
    out = []
    if struck:
        s = "".join(f'<span style="display:inline-block;transform:rotate({rng.uniform(-5,5):.1f}deg)">{html.escape(c)}</span>' for c in struck)
        out.append(f'<span style="position:relative;margin-right:10px;opacity:{op:.2f};color:{ink};font-family:&quot;{font}&quot;;font-size:{size}px">{s}'
                   f'<span style="position:absolute;left:-3px;right:-3px;top:52%;border-top:2.5px solid {ink};transform:rotate({rng.uniform(-8,8):.0f}deg)"></span></span>')
    chars = []
    for c in text:
        chars.append(f'<span style="display:inline-block;transform:translateY({rng.uniform(-2.5,2.5):.1f}px) rotate({rng.uniform(-7,7):.1f}deg);'
                     f'font-size:{size * rng.uniform(0.88, 1.12):.0f}px;margin-right:{rng.uniform(-2.5,1.5):.1f}px">{html.escape(c)}</span>')
    out.append(f'<span style="font-family:\'{font}\';color:{ink};opacity:{op:.2f};filter:blur(0.35px);'
               f'display:inline-block;transform:rotate({rng.uniform(-4,4):.1f}deg)">{"".join(chars)}</span>')
    return "".join(out)


def make_values(rng, n_items, layout):
    rows = []
    for i, item in enumerate(rng.sample(ITEMS, n_items)):
        d = rng.choice([1, 2, 2, 3, 3])
        nominal = rng.choice([3.2, 5.0, 8.5, 12.0, 12.5, 18.0, 25.0, 30.0, 42.5, 60.0]) + rng.choice([0, 0, 0.25, 0.5])
        if rng.random() < 0.6:
            tp = tm = rng.choice([0.01, 0.02, 0.03, 0.05, 0.1])
            tm = -tm
        else:
            tp, tm = rng.choice([(0.05, -0.02), (0.03, -0.01), (0.1, 0.0), (0.0, -0.05), (0.02, -0.04)])
        td = 2 if max(abs(tp), abs(tm)) >= 0.01 else 3
        meas = [nominal + rng.gauss(0, (tp - tm) / 3) for _ in range(3 if layout == "B" else 1)]
        rows.append({"row": i + 1, "item": item, "d": d, "nominal": num(nominal, d), "tol_plus": num(tp, td), "tol_minus": num(tm, td),
                     "measured": [num(m, d) for m in meas], "deviation": num(meas[0] - nominal, d)})
    return rows


def sign(s):
    return s if s.startswith("-") else ("+" + s if float(s) > 0 else s)


def page(rng, sheet_id, layout, rows, writer, faint_cells, corrections):
    """Build the sheet HTML and the answer rows."""
    ans = []
    cell = lambda key, text, kind: (ans.append((key, text, kind)),
                                    hand(rng, text.replace("-", "−") if rng.random() < 0.5 else text, writer,
                                         faint=key in faint_cells, struck=corrections.get(key)))[1]
    th = "border:1.5px solid #333;padding:6px 8px;background:#f1f1ec;font-weight:600"
    td = "border:1.2px solid #444;padding:4px 8px;height:58px;vertical-align:middle"
    body = []
    if layout == "A":
        head = ["No", "측정 항목", "기준값", "공차 (+)", "공차 (−)", "측정값", "판정"]
        for r in rows:
            ok = float(r["tol_minus"]) <= float(r["measured"][0]) - float(r["nominal"]) <= float(r["tol_plus"])
            body.append([str(r["row"]), r["item"],
                         cell((r["item"], "nominal", 0), r["nominal"], "nominal"),
                         cell((r["item"], "tol_plus", 0), sign(r["tol_plus"]), "tol_plus"),
                         cell((r["item"], "tol_minus", 0), r["tol_minus"], "tol_minus"),
                         cell((r["item"], "measured", 0), r["measured"][0], "measured"),
                         hand(rng, "OK" if ok else "NG", writer)])
    elif layout == "B":
        head = ["측정 항목", "규격", "X1", "X2", "X3", "판정"]
        for r in rows:
            spec = f'{r["nominal"]} ({sign(r["tol_plus"])} / {r["tol_minus"]})'
            ans.append(((r["item"], "nominal", 0), r["nominal"], "printed"))
            ans.append(((r["item"], "tol_plus", 0), sign(r["tol_plus"]), "printed"))
            ans.append(((r["item"], "tol_minus", 0), r["tol_minus"], "printed"))
            body.append([r["item"], f'<span style="font-family:\'Malgun Gothic\';font-size:19px">{html.escape(spec)}</span>'] +
                        [cell((r["item"], "measured", k), m, "measured") for k, m in enumerate(r["measured"])] +
                        [hand(rng, "합" if all(float(r["tol_minus"]) <= float(m) - float(r["nominal"]) <= float(r["tol_plus"]) for m in r["measured"]) else "불", writer)])
    else:
        head = ["측정 항목", "도면 치수", "공차", "실측", "편차"]
        for r in rows:
            tol = f'{sign(r["tol_plus"])} / {r["tol_minus"]}'
            ans.append(((r["item"], "tol_plus", 0), sign(r["tol_plus"]), "tol_plus"))
            ans.append(((r["item"], "tol_minus", 0), r["tol_minus"], "tol_minus"))
            body.append([r["item"], cell((r["item"], "nominal", 0), r["nominal"], "nominal"), hand(rng, tol, writer),
                         cell((r["item"], "measured", 0), r["measured"][0], "measured"),
                         cell((r["item"], "deviation", 0), sign(r["deviation"]), "deviation")])
    table = ("<table style='border-collapse:collapse;width:100%;font-family:\"Malgun Gothic\";font-size:20px'>"
             + "<tr>" + "".join(f"<th style='{th}'>{h}</th>" for h in head) + "</tr>"
             + "".join("<tr>" + "".join(f"<td style='{td}'>{c}</td>" for c in r) + "</tr>" for r in body) + "</table>")
    drawing = f"DWG-2026-{rng.randint(100, 999)}"
    light = f"radial-gradient(ellipse at {rng.randint(20,80)}% {rng.randint(10,60)}%, #fffefa 0%, #f3f0e6 55%, #e4dfd2 100%)"
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:#cfcabd}}</style></head>
<body><div style="position:absolute;inset:28px;background:{light};transform:rotate({rng.uniform(-1.6,1.6):.2f}deg) skewX({rng.uniform(-1,1):.2f}deg);
box-shadow:0 0 18px rgba(0,0,0,.35);padding:56px 60px;box-sizing:border-box">
<div style="font-family:'Malgun Gothic';font-size:34px;font-weight:700;text-align:center;letter-spacing:6px">측 정 기 록 지</div>
<div style="font-family:'Malgun Gothic';font-size:19px;margin:26px 0 18px;display:flex;justify-content:space-between">
<span>회사: (가상) 샘플 제작소</span><span>도면 번호: {drawing}</span><span>양식 {layout}</span></div>
<div style="font-family:'Malgun Gothic';font-size:19px;margin-bottom:22px">측정일: {hand(rng, f"11/{rng.randint(1,26)}", writer)} &nbsp;&nbsp; 측정자: {hand(rng, rng.choice(["김", "이", "박", "최"]) + "OO", writer)} &nbsp;&nbsp; 단위: mm</div>
{table}
<div style="font-family:'Malgun Gothic';font-size:16px;color:#555;margin-top:24px">※ 합성 실험용 가상 측정지 (실제 자료 아님) · {sheet_id}</div>
</div></body></html>"""
    return doc, ans, drawing


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    answers = []
    meta = []
    hard = set(rng.sample(range(SHEETS), 6))       # 6 sheets with faint cells and a correction
    tmp = Path(tempfile.mkdtemp(prefix="cel040-"))
    try:
        for i in range(SHEETS):
            sid = f"S{i + 1:02d}"
            layout = "ABC"[i // 10]
            writer = WRITERS[i % 3]
            rows = make_values(rng, rng.randint(6, 8) if layout != "B" else rng.randint(5, 7), layout)
            faint, corr = set(), {}
            if i in hard:
                r = rng.choice(rows)
                faint.add((r["item"], "measured", 0))
                r2 = rng.choice(rows)
                wrong = r2["measured"][0][:-1] + str((int(r2["measured"][0][-1]) + 3) % 10)
                corr[(r2["item"], "measured", 0)] = wrong
            doc, ans, drawing = page(rng, sid, layout, rows, writer, faint, corr)
            html_path = tmp / f"{sid}.html"
            html_path.write_text(doc, encoding="utf-8")
            png = out / f"{sid}.png"
            subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={tmp / 'edge'}",
                            f"--window-size={W},{H}", f"--screenshot={png}", html_path.as_uri()],
                           check=True, capture_output=True, timeout=120)
            for n, ((item, kind, k), value, how) in enumerate(ans):
                answers.append({"sheet_id": sid, "field_id": f"{sid}-{n + 1:02d}", "spec_item": item, "kind": kind, "index": k,
                                "value": value, "unit": "mm", "handwritten": how != "printed",
                                "faint": (item, kind, k) in faint, "corrected": (item, kind, k) in corr})
            meta.append({"sheet_id": sid, "layout": layout, "writer": writer[0], "hard": i in hard, "drawing_no": drawing,
                         "rows": len(rows), "fields": len(ans)})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    with (out / "answers.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["sheet_id", "field_id", "spec_item", "kind", "index", "value", "unit", "handwritten", "faint", "corrected"])
        w.writeheader()
        w.writerows(answers)
    with (out / "sheets.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(meta[0]))
        w.writeheader()
        w.writerows(meta)
    print(f"{SHEETS} sheets, {len(answers)} fields -> {out}")


if __name__ == "__main__":
    main(sys.argv[1])
