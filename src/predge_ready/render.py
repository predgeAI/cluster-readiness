"""Render a report as JSON, Markdown and a self-contained HTML page."""

from __future__ import annotations

import html
import json
from typing import Any, Dict, List

LABEL = (
    "Independent readiness estimate against the published ClusterMAX criteria. "
    "Not a SemiAnalysis rating and not affiliated with SemiAnalysis; ClusterMAX is a SemiAnalysis trademark."
)

CHECK_WORD = {"pass": "Pass", "warn": "Warn", "fail": "Fail", "na": "N/A", "unknown": "Unknown"}


def to_json(report: Dict[str, Any]) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def _md_escape(s: Any) -> str:
    return str(s if s is not None else "").replace("|", "\\|").replace("\n", " ")


def to_markdown(r: Dict[str, Any]) -> str:
    s = r["score"]
    L: List[str] = []
    L.append(f"# Cluster readiness report: {r['cluster']['name']}")
    L.append("")
    L.append(f"> {LABEL}")
    L.append("")
    L.append(f"Generated {r['generated_at']} by predge-ready {r['tool']['version']} ({r['mode']}). Nodes scanned: {len(r['nodes'])}.")
    if r.get("expect"):
        L.append(f"Expected: {', '.join(f'{k}={v}' for k, v in r['expect'].items())}.")
    L.append("")
    L.append("## Summary")
    L.append("")
    L.append(f"- Readiness index (all {s['total']} criteria, Unknown = 0): **{s['index']}%**")
    if s.get("assessed_index") is not None:
        L.append(f"- Index over the {s['assessed']} criteria this scan could evidence: **{s['assessed_index']}%**")
    c = s["counts"]
    L.append(f"- Meets {c['Meets']} · Partial {c['Partial']} · Gap {c['Gap']} · Unknown {c['Unknown']}")
    h = r["health"]
    L.append(f"- Node health: {h['healthy']} healthy, {h['warning']} warning, {h['failing']} failing")
    L.append("")
    L.append("## Top fixes")
    L.append("")
    if not r["top_fixes"]:
        L.append("No failing or warning checks.")
    for i, f in enumerate(r["top_fixes"], 1):
        nodes = f" Nodes: {', '.join(f['nodes'][:6])}." if f["nodes"] and f["nodes"] != ["cluster"] else ""
        crit = f" Criteria: {', '.join(f['criteria'])}." if f["criteria"] else ""
        L.append(f"{i}. **{f['title']}** ({CHECK_WORD[f['status']]}). {f['fix']}{crit}{nodes}")
    L.append("")
    L.append("## Categories")
    L.append("")
    L.append("| Category | Rows | Meets | Partial | Gap | Unknown | Index |")
    L.append("|---|---|---|---|---|---|---|")
    for cat in s["categories"]:
        k = cat["counts"]
        L.append(f"| {cat['name']} | {cat['rows']} | {k['Meets']} | {k['Partial']} | {k['Gap']} | {k['Unknown']} | {cat['index']}% |")
    L.append("")
    L.append("## Node checks")
    L.append("")
    L.append("| Check | Status | Nodes affected | Detail | Criteria |")
    L.append("|---|---|---|---|---|")
    for chk in r["checks"]:
        aff = ", ".join(chk["nodes_affected"][:6]) if chk["nodes_affected"] else ""
        L.append(f"| {_md_escape(chk['title'])} | {CHECK_WORD[chk['status']]} | {_md_escape(aff)} | {_md_escape(chk['reason'])} | {', '.join(chk['criteria'])} |")
    L.append("")
    L.append("## Nodes")
    L.append("")
    L.append("| Node | GPUs | Driver / CUDA | Fabric | Health |")
    L.append("|---|---|---|---|---|")
    for n in r["nodes"]:
        inv = n["inventory"]
        L.append(f"| {n['host']} | {_md_escape(inv['gpus'])} | {inv['driver'] or '-'} / {inv['cuda'] or '-'} | {_md_escape(inv['fabric'])} | {n['health']} |")
    L.append("")
    L.append("## Criteria")
    L.append("")
    L.append("| ID | Category | Criterion | Status | Basis | Note |")
    L.append("|---|---|---|---|---|---|")
    for row in s["rows"]:
        L.append(f"| {row['id']} | {row['category']} | {_md_escape(row['criterion'])} | {row['status']} | {row['basis']} | {_md_escape(row['note'])} |")
    L.append("")
    if r.get("notes"):
        L.append("## Notes")
        L.append("")
        for n in r["notes"]:
            L.append(f"- {n}")
        L.append("")
    if r.get("signature"):
        sg = r["signature"]
        L.append(f"Signed (ed25519) by {sg['fingerprint']} at {sg['signed_at']}. Verify with `predge-ready verify report.json`.")
        L.append("")
    L.append("---")
    L.append("Method: the index counts Meets as 1 and Partial as 0.5 over all criteria rows. Unknown is not a failure; most Unknown rows are policy, commercial or provider-level items a node cannot show. " + LABEL)
    return "\n".join(L) + "\n"


CSS = """
:root{--bg:#ffffff;--fg:#1d1f23;--muted:#5f6673;--line:#e3e6eb;--soft:#f6f7f9;
--pass:#1f7a3f;--pass-bg:#e6f4ea;--warn:#8a5a00;--warn-bg:#fff4d6;--fail:#b3261e;--fail-bg:#fde7e5;--unk:#5f6673;--unk-bg:#eef0f3}
*{box-sizing:border-box}
html{color-scheme:light}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
main{max-width:1120px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:26px;margin:0 0 4px;font-weight:650;letter-spacing:-.01em}
h2{font-size:18px;margin:36px 0 12px;font-weight:650}
.sub{color:var(--muted);margin:0 0 16px}
.label{border:1px solid var(--line);background:var(--soft);padding:10px 14px;border-radius:8px;font-size:13.5px;color:var(--muted)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-top:20px}
.card{border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.card .k{font-size:12.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.card .v{font-size:30px;font-weight:650;margin-top:2px;font-variant-numeric:tabular-nums}
.card .s{font-size:13px;color:var(--muted)}
.bar{height:8px;background:var(--soft);border-radius:4px;overflow:hidden;display:flex;margin-top:8px}
.bar i{display:block;height:100%}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-weight:600;color:var(--muted);font-size:12.5px;text-transform:uppercase;letter-spacing:.03em;background:var(--soft)}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.wrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px}
.pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap}
.p-pass,.p-Meets{color:var(--pass);background:var(--pass-bg)}
.p-warn,.p-Partial{color:var(--warn);background:var(--warn-bg)}
.p-fail,.p-Gap{color:var(--fail);background:var(--fail-bg)}
.p-unknown,.p-Unknown,.p-na{color:var(--unk);background:var(--unk-bg)}
ol.fixes{padding-left:22px;margin:0}
ol.fixes li{margin:0 0 10px}
.muted{color:var(--muted)}
.small{font-size:12.5px}
code{font:12.5px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--soft);padding:1px 5px;border-radius:4px}
details{margin-top:8px}
summary{cursor:pointer;color:var(--muted)}
footer{margin-top:40px;font-size:12.5px;color:var(--muted);border-top:1px solid var(--line);padding-top:14px}
@media (max-width:640px){.card .v{font-size:24px}th:nth-child(5),td:nth-child(5){display:none}}
"""


def _e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def _pill(status: str, text: str = "") -> str:
    return f'<span class="pill p-{_e(status)}">{_e(text or CHECK_WORD.get(status, status))}</span>'


def to_html(r: Dict[str, Any]) -> str:
    s = r["score"]
    c = s["counts"]
    h = r["health"]
    tot = s["total"] or 1
    bar = "".join(
        f'<i style="width:{100.0 * c[k] / tot:.2f}%;background:var({v})" title="{k} {c[k]}"></i>'
        for k, v in (("Meets", "--pass"), ("Partial", "--warn"), ("Gap", "--fail"), ("Unknown", "--line"))
    )
    out: List[str] = []
    a = out.append
    a("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">")
    a(f"<title>Cluster readiness: {_e(r['cluster']['name'])}</title><style>{CSS}</style></head><body><main>")
    a(f"<h1>Cluster readiness: {_e(r['cluster']['name'])}</h1>")
    exp = (" · expected " + _e(", ".join(f"{k}={v}" for k, v in r["expect"].items()))) if r.get("expect") else ""
    a(f'<p class="sub">Generated {_e(r["generated_at"])} · predge-ready {_e(r["tool"]["version"])} · {_e(r["mode"])} · {len(r["nodes"])} node(s){exp}</p>')
    a(f'<div class="label">{_e(LABEL)}</div>')
    a('<div class="cards">')
    a(f'<div class="card"><div class="k">Readiness index</div><div class="v">{s["index"]}%</div><div class="s">all {s["total"]} criteria, Unknown = 0</div><div class="bar">{bar}</div></div>')
    if s.get("assessed_index") is not None:
        a(f'<div class="card"><div class="k">Evidenced criteria</div><div class="v">{s["assessed_index"]}%</div><div class="s">over the {s["assessed"]} rows this scan could measure</div></div>')
    a(f'<div class="card"><div class="k">Criteria</div><div class="v" style="font-size:20px;margin-top:8px">{_pill("Meets", "Meets " + str(c["Meets"]))} {_pill("Partial", "Partial " + str(c["Partial"]))} {_pill("Gap", "Gap " + str(c["Gap"]))} {_pill("Unknown", "Unknown " + str(c["Unknown"]))}</div></div>')
    a(f'<div class="card"><div class="k">Node health</div><div class="v">{h["failing"]}<span class="s"> failing</span></div><div class="s">{h["healthy"]} healthy · {h["warning"]} warning · {len(r["nodes"])} scanned</div></div>')
    a("</div>")

    a("<h2>Top fixes</h2>")
    if r["top_fixes"]:
        a('<ol class="fixes">')
        for f in r["top_fixes"]:
            nodes = f' <span class="muted small">Nodes: {_e(", ".join(f["nodes"][:6]))}</span>' if f["nodes"] and f["nodes"] != ["cluster"] else ""
            crit = f' <span class="muted small">Criteria: {_e(", ".join(f["criteria"]))}</span>' if f["criteria"] else ""
            a(f'<li>{_pill(f["status"])} <strong>{_e(f["title"])}</strong>. {_e(f["fix"])}{crit}{nodes}</li>')
        a("</ol>")
    else:
        a('<p class="muted">No failing or warning checks.</p>')

    a("<h2>Categories</h2><div class=\"wrap\"><table><thead><tr><th>Category</th><th>Rows</th><th>Meets</th><th>Partial</th><th>Gap</th><th>Unknown</th><th>Index</th></tr></thead><tbody>")
    for cat in s["categories"]:
        k = cat["counts"]
        w = cat["rows"] or 1
        mini = "".join(f'<i style="width:{100.0 * k[n] / w:.1f}%;background:var({v})"></i>' for n, v in (("Meets", "--pass"), ("Partial", "--warn"), ("Gap", "--fail")))
        a(f'<tr><td>{_e(cat["name"])}<div class="bar" style="max-width:220px">{mini}</div></td><td class="num">{cat["rows"]}</td><td class="num">{k["Meets"]}</td><td class="num">{k["Partial"]}</td><td class="num">{k["Gap"]}</td><td class="num">{k["Unknown"]}</td><td class="num">{cat["index"]}%</td></tr>')
    a("</tbody></table></div>")

    a("<h2>Node checks</h2><div class=\"wrap\"><table><thead><tr><th>Check</th><th>Status</th><th>Nodes affected</th><th>Detail</th><th>Criteria</th></tr></thead><tbody>")
    order = {"fail": 0, "warn": 1, "unknown": 2, "pass": 3, "na": 4}
    for chk in sorted(r["checks"], key=lambda x: (order.get(x["status"], 5), x["id"])):
        aff = ", ".join(chk["nodes_affected"][:6])
        if len(chk["nodes_affected"]) > 6:
            aff += f" +{len(chk['nodes_affected']) - 6}"
        src = ' <span class="muted small">(cmax)</span>' if chk.get("source") == "cmax" else ""
        a(f'<tr><td>{_e(chk["title"])}{src}</td><td>{_pill(chk["status"])}</td><td>{_e(aff)}</td><td>{_e(chk["reason"])}</td><td class="small">{_e(", ".join(chk["criteria"]))}</td></tr>')
    a("</tbody></table></div>")

    a("<h2>Nodes</h2><div class=\"wrap\"><table><thead><tr><th>Node</th><th>GPUs</th><th>Driver / CUDA</th><th>Fabric</th><th>Health</th></tr></thead><tbody>")
    for n in r["nodes"]:
        inv = n["inventory"]
        hs = {"healthy": "pass", "warning": "warn", "failing": "fail"}.get(n["health"], "unknown")
        a(f'<tr><td>{_e(n["host"])}</td><td>{_e(inv["gpus"])}</td><td>{_e(inv["driver"] or "-")} / {_e(inv["cuda"] or "-")}</td><td>{_e(inv["fabric"])}</td><td>{_pill(hs, n["health"])}</td></tr>')
    a("</tbody></table></div>")

    a("<h2>ClusterMAX criteria</h2>")
    a('<p class="muted small">Basis: <em>measured</em> from this scan, <em>self-attested</em> from an answers file, <em>not node-observable</em> for policy, commercial and provider-level rows.</p>')
    a("<div class=\"wrap\"><table><thead><tr><th>ID</th><th>Criterion</th><th>Status</th><th>Basis</th><th>Note</th></tr></thead><tbody>")
    cur = None
    for row in s["rows"]:
        if row["category"] != cur:
            cur = row["category"]
            a(f'<tr><td colspan="5" style="background:var(--soft);font-weight:600">{_e(cur)}</td></tr>')
        a(f'<tr><td class="num">{_e(row["id"])}</td><td>{_e(row["criterion"])}</td><td>{_pill(row["status"])}</td><td class="small muted">{_e(row["basis"])}</td><td class="small">{_e(row["note"])}</td></tr>')
    a("</tbody></table></div>")

    if r.get("notes"):
        a("<h2>Notes</h2><ul>" + "".join(f"<li>{_e(n)}</li>" for n in r["notes"]) + "</ul>")
    a("<footer>")
    if r.get("signature"):
        sg = r["signature"]
        a(f'<p>Signed with Ed25519 by <code>{_e(sg["fingerprint"])}</code> at {_e(sg["signed_at"])}. Verify the JSON with <code>predge-ready verify report.json</code>.</p>')
    a("<p>Method: Meets = 1, Partial = 0.5, Gap and Unknown = 0, over every criteria row. Unknown is not a failure; most Unknown rows are policy, commercial or provider-level items a node cannot show. "
      "This report was produced locally on the operator's machine; nothing was sent anywhere.</p>")
    a(f"<p>{_e(LABEL)}</p></footer></main></body></html>")
    return "\n".join(out)
