"""Render an InfraFit report (the dict cli.py prints with --json) as one HTML or Markdown file.

Only decision outputs and thresholds.json are used, so input fields the rules do not
emit (account IDs, ARNs, query text) cannot appear. Every value is escaped. No
timestamp is written: the same input gives the same file.
"""
from collections import Counter, OrderedDict
from decimal import Decimal
import html
import json

ORDER = ("candidate", "keep", "hold")
LABELS = {"candidate": "변경 검토 후보", "keep": "유지", "hold": "판단 보류"}
KIND = {"synthetic": "합성", "real": "실제"}
NOTICE = ["예상 절감은 실제 청구 절감이 아닙니다. 공개 요율과 입력 사용량으로 계산한 값입니다.",
          "실제 청구 대사: 미검증"]


def data_kind_label(kinds):
    """kinds: list of (source, kind). Returns a label like '합성' or '혼합 (합성·실제)'."""
    values = sorted({k for _, k in kinds}, key=lambda k: (k != "synthetic", k))
    names = [KIND.get(k, k) for k in values]
    return names[0] if len(names) == 1 else f"혼합 ({'·'.join(names)})"


def threshold_entry(thresholds, key):
    section, _, name = key.partition(".")
    entry = (thresholds.get(section) or {}).get(name)
    return entry if isinstance(entry, dict) else None


def build(report, thresholds, kinds, reason_text):
    """Collect everything both formats show, in display order."""
    base = [{"rule": "EC2·EBS", "id": d["address"], "decision": d["decision"],
             "reasons": d["reasons"], "evidence": _base_evidence(d), "saving": None, "basis": None, "used": []}
            for d in report["decisions"]]
    work = [{"rule": d["rule"], "id": d["id"], "decision": d["decision"], "reasons": d["reasons"],
             "evidence": d.get("evidence") or {}, "saving": d.get("expected_saving_usd"), "basis": d.get("saving_basis"),
             "used": d.get("thresholds_used") or []} for d in report.get("workload_decisions", [])]
    items = base + work
    rules = OrderedDict()
    for it in items:
        r = rules.setdefault(it["rule"], {"counts": Counter(), "savings": OrderedDict()})
        r["counts"][it["decision"]] += 1
        if it["saving"]:
            r["savings"][it["basis"]] = r["savings"].get(it["basis"], Decimal(0)) + Decimal(it["saving"])
    holds = OrderedDict()
    for it in items:
        if it["decision"] == "hold":
            for reason in it["reasons"]:
                holds.setdefault(reason, []).append(f"{it['rule']} {it['id']}")
    used = OrderedDict()
    for it in items:
        for key in it["used"]:
            entry = threshold_entry(thresholds, key)
            if entry is not None:
                used[key] = entry
    return {"kind": data_kind_label(kinds), "kinds": kinds, "window": report.get("window"), "as_of": report.get("as_of"),
            "summary": {"EC2·EBS 판정": Counter(i["decision"] for i in base),
                        "워크로드 규칙": Counter(i["decision"] for i in work)},
            "rules": rules, "items": items, "holds": holds, "reason_text": reason_text,
            "queue": report.get("investigation_queue"), "queue_holds": report.get("investigation_holds"),
            "used": used, "thresholds": thresholds, "unassigned": report.get("unassigned_missing_id_rows", 0)}


def _base_evidence(d):
    ev = {}
    if d.get("modeled_usd"):
        ev.update({f"가상 USD {k}": v for k, v in d["modeled_usd"].items()})
    if d.get("peak_p99_ms") is not None:
        ev["peak_p99_ms"] = d["peak_p99_ms"]
    if d.get("plan_status"):
        ev["plan_status"] = d["plan_status"]
    return ev


def _fmt(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else str(value)


def _money(x):
    return format(x.quantize(Decimal("0.000001")), "f")


# ---------------------------------------------------------------- Markdown
def to_markdown(data):
    md = lambda x: _fmt(x).replace("|", "\\|").replace("\n", " ")
    out = ["# InfraFit 보고서", ""]
    out += [f"> {n}" for n in NOTICE] + [""]
    out += [f"- 입력 데이터: **{data['kind']}** ({', '.join(f'{md(s)}: {KIND.get(k, k)}' for s, k in data['kinds'])})",
            f"- 평가 기간·시점: {md(data['window'])} / {md(data['as_of'])}", ""]
    out += ["## 요약", "", "| 구분 | 변경 검토 후보 | 유지 | 판단 보류 |", "|---|---:|---:|---:|"]
    out += [f"| {g} | {c['candidate']} | {c['keep']} | {c['hold']} |" for g, c in data["summary"].items()]
    out += ["", "예상 절감은 계산 기준(월·관측 기간 등)이 같은 항목끼리만 더한다. 기준이 다르면 줄을 나눈다.", "",
            "## 규칙별", "", "| 규칙 | 후보 | 유지 | 보류 | 예상 절감 USD | 계산 기준 |", "|---|---:|---:|---:|---:|---|"]
    for rule, r in data["rules"].items():
        c = r["counts"]
        lines = list(r["savings"].items()) or [(None, None)]
        for i, (basis, amount) in enumerate(lines):
            head = f"| {md(rule)} | {c['candidate']} | {c['keep']} | {c['hold']} |" if i == 0 else "| | | | |"
            out.append(f"{head} {_money(amount) if amount is not None else ''} | {md(basis)} |")
    out += ["", "## 항목별", ""]
    for it in data["items"]:
        out.append(f"### {md(it['rule'])} · {md(it['id'])} — {LABELS[it['decision']]}")
        out += [f"- 이유: {md(data['reason_text'].get(r, r))}" for r in it["reasons"]]
        if it["evidence"]:
            out.append("- 근거: " + ", ".join(f"`{md(k)}` {md(v)}" for k, v in it["evidence"].items()))
        if it["saving"]:
            out.append(f"- 예상 절감 USD {md(it['saving'])} ({md(it['basis'])})")
        for key in it["used"]:
            e = threshold_entry(data["thresholds"], key)
            if e:
                out.append(f"- 기준값 `{md(key)}` = {md(e.get('value'))} ({md(e.get('evidence'))})")
        out.append("")
    out += ["## 판단 보류 사유", ""]
    if not data["holds"]:
        out.append("판단 보류 항목이 없다.")
    for reason, ids in data["holds"].items():
        out.append(f"- **{md(data['reason_text'].get(reason, reason))}** — {md(', '.join(ids))}")
    out.append("")
    if data["queue"] is not None:
        out += ["## 비용 급증 조사 대기열 (판정이 아니라 조사 대상)", "",
                "| 서비스 | 날짜 | 관측 USD | 기준 중앙값 USD | 경보 기준 USD | 잠정 |", "|---|---|---:|---:|---:|---|"]
        out += [f"| {md(q['service'])} | {md(q['date'])} | {md(q['observed_usd'])} | {md(q['baseline_median_usd'])} | "
                f"{md(q['threshold_usd'])} | {'잠정' if q['estimated'] else ''} |" for q in data["queue"]]
        out += [""] + [f"- {md(h['service'])}: 판단 보류 — {md(h['message'])}" for h in data["queue_holds"] or []] + [""]
    out += ["## 사용한 기준값", "", "| 기준값 | 값 | 근거 수준 | 출처 |", "|---|---|---|---|"]
    out += [f"| `{md(k)}` | {md(e.get('value'))} | {md(e.get('evidence'))} | {md(e.get('source'))} |" for k, e in data["used"].items()]
    if data["unassigned"]:
        out += ["", f"행 ID와 자원 ID를 확인할 수 없는 청구 행: {data['unassigned']}건 (비용 집계 제외)"]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- HTML
CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#5f5e58;--line:#dedbd2;--card:#ffffff;--cand:#1f6f4a;--keep:#3d5a80;--hold:#9a5b13;--note:#fff4dc}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--fg:#ecebe6;--muted:#a8a69d;--line:#34332f;--card:#1f1f1c;--cand:#6fcf9f;--keep:#9db8de;--hold:#e3a65a;--note:#3a2f17}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,-apple-system,"Segoe UI","Apple SD Gothic Neo","Malgun Gothic",sans-serif;word-break:keep-all;overflow-wrap:anywhere}
main{max-width:1040px;margin:0 auto;padding:32px 16px 64px}h1{font-size:28px;margin:0 0 8px}h2{font-size:20px;margin:40px 0 12px;padding-top:8px;border-top:1px solid var(--line)}
h3{font-size:16px;margin:0 0 6px}.meta{color:var(--muted);margin:4px 0}.notice{background:var(--note);border-radius:8px;padding:12px 16px;margin:16px 0}
.notice p{margin:2px 0;font-weight:600}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{border-bottom:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}th{color:var(--muted);font-weight:600;white-space:nowrap}td.n{text-align:right}
td.n,td:first-child{white-space:nowrap;overflow-wrap:normal}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.tile{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}
.tile b{display:block;font-size:26px}.candidate{color:var(--cand)}.keep{color:var(--keep)}.hold{color:var(--hold)}
.item{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin:10px 0}.item ul{margin:4px 0;padding-left:20px}
code{font-family:ui-monospace,Consolas,monospace;font-size:13px}.tag{font-size:13px;font-weight:600}
"""


def to_html(data):
    e = lambda x: html.escape(_fmt(x))
    parts = ["<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">",
             "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>InfraFit 보고서</title>",
             f"<style>{CSS}</style></head><body><main>", "<h1>InfraFit 보고서</h1>",
             f"<p class=\"meta\">입력 데이터: <b>{e(data['kind'])}</b> — "
             + ", ".join(f"{e(s)}: {e(KIND.get(k, k))}" for s, k in data["kinds"]) + "</p>",
             f"<p class=\"meta\">평가 기간·시점: {e(data['window'])} / {e(data['as_of'])}</p>",
             "<div class=\"notice\">" + "".join(f"<p>{e(n)}</p>" for n in NOTICE) + "</div>", "<h2>요약</h2>"]
    for group, c in data["summary"].items():
        parts.append(f"<h3>{e(group)}</h3><div class=\"tiles\">" + "".join(
            f"<div class=\"tile\"><span class=\"{s}\">{LABELS[s]}</span><b class=\"{s}\">{c[s]}</b></div>" for s in ORDER) + "</div>")
    parts.append("<p class=\"meta\">예상 절감은 계산 기준(월·관측 기간 등)이 같은 항목끼리만 더한다. 기준이 다르면 줄을 나눈다.</p>")
    parts.append("<h2>규칙별</h2><div class=\"scroll\"><table><thead><tr><th>규칙</th><th>후보</th><th>유지</th><th>보류</th>"
                 "<th>예상 절감 USD</th><th>계산 기준</th></tr></thead><tbody>")
    for rule, r in data["rules"].items():
        c = r["counts"]
        lines = list(r["savings"].items()) or [(None, None)]
        span = f" rowspan=\"{len(lines)}\"" if len(lines) > 1 else ""
        for i, (basis, amount) in enumerate(lines):
            head = (f"<td{span}>{e(rule)}</td><td class=\"n\"{span}>{c['candidate']}</td><td class=\"n\"{span}>{c['keep']}</td>"
                    f"<td class=\"n\"{span}>{c['hold']}</td>") if i == 0 else ""
            parts.append(f"<tr>{head}<td class=\"n\">{_money(amount) if amount is not None else ''}</td><td>{e(basis)}</td></tr>")
    parts.append("</tbody></table></div><h2>항목별</h2>")
    for it in data["items"]:
        rows = [f"<li>이유: {e(data['reason_text'].get(r, r))}</li>" for r in it["reasons"]]
        if it["evidence"]:
            rows.append("<li>근거: " + ", ".join(f"<code>{e(k)}</code> {e(v)}" for k, v in it["evidence"].items()) + "</li>")
        if it["saving"]:
            rows.append(f"<li>예상 절감 USD {e(it['saving'])} ({e(it['basis'])})</li>")
        for key in it["used"]:
            t = threshold_entry(data["thresholds"], key)
            if t:
                rows.append(f"<li>기준값 <code>{e(key)}</code> = {e(t.get('value'))} ({e(t.get('evidence'))})</li>")
        parts.append(f"<div class=\"item\"><h3>{e(it['rule'])} · {e(it['id'])} "
                     f"<span class=\"tag {it['decision']}\">{LABELS[it['decision']]}</span></h3><ul>{''.join(rows)}</ul></div>")
    parts.append("<h2>판단 보류 사유</h2>")
    if not data["holds"]:
        parts.append("<p>판단 보류 항목이 없다.</p>")
    else:
        parts.append("<ul>" + "".join(f"<li><b>{e(data['reason_text'].get(r, r))}</b> — {e(', '.join(ids))}</li>"
                                     for r, ids in data["holds"].items()) + "</ul>")
    if data["queue"] is not None:
        parts.append("<h2>비용 급증 조사 대기열 <span class=\"meta\">판정이 아니라 조사 대상</span></h2><div class=\"scroll\"><table>"
                     "<thead><tr><th>서비스</th><th>날짜</th><th>관측 USD</th><th>기준 중앙값 USD</th><th>경보 기준 USD</th>"
                     "<th>잠정</th></tr></thead><tbody>")
        parts += [f"<tr><td>{e(q['service'])}</td><td>{e(q['date'])}</td><td class=\"n\">{e(q['observed_usd'])}</td>"
                  f"<td class=\"n\">{e(q['baseline_median_usd'])}</td><td class=\"n\">{e(q['threshold_usd'])}</td>"
                  f"<td>{'잠정' if q['estimated'] else ''}</td></tr>" for q in data["queue"]]
        parts.append("</tbody></table></div>")
        if data["queue_holds"]:
            parts.append("<ul>" + "".join(f"<li>{e(h['service'])}: 판단 보류 — {e(h['message'])}</li>"
                                         for h in data["queue_holds"]) + "</ul>")
    parts.append("<h2>사용한 기준값</h2><div class=\"scroll\"><table><thead><tr><th>기준값</th><th>값</th><th>근거 수준</th>"
                 "<th>출처</th></tr></thead><tbody>")
    parts += [f"<tr><td><code>{e(k)}</code></td><td>{e(t.get('value'))}</td><td>{e(t.get('evidence'))}</td>"
              f"<td>{e(t.get('source'))}</td></tr>" for k, t in data["used"].items()]
    parts.append("</tbody></table></div>")
    if data["unassigned"]:
        parts.append(f"<p>행 ID와 자원 ID를 확인할 수 없는 청구 행: {e(data['unassigned'])}건 (비용 집계 제외)</p>")
    parts.append("</main></body></html>")
    return "\n".join(parts) + "\n"


def render(report, thresholds, kinds, reason_text, fmt):
    data = build(report, thresholds, kinds, reason_text)
    return to_html(data) if fmt == "html" else to_markdown(data)
