"""Map check results onto the ClusterMAX criteria rows and score them.

Status per row: Meets / Partial / Gap / Unknown.
Readiness index = (Meets + 0.5 * Partial) / all rows, the same simple index
used in Predge's outside-in gap reports. Unknown counts as 0; it is not a
failure, it means the row was not evidenced.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from importlib import resources
from typing import Any, Dict, List, Optional

from .checks import FAIL, HEALTH_IDS, HEALTH_PRIORITY, NA, PASS, SEVERITY, UNKNOWN, WARN

MEETS, PARTIAL, GAP, UNK = "Meets", "Partial", "Gap", "Unknown"
STATUSES = (MEETS, PARTIAL, GAP, UNK)


def load_criteria() -> List[Dict[str, str]]:
    return json.loads(resources.files("predge_ready").joinpath("data/criteria.json").read_text())["criteria"]


def worst(statuses: List[str]) -> str:
    """Aggregate one check across nodes: the worst known status wins."""
    known = [s for s in statuses if s != UNKNOWN]
    if not known:
        return UNKNOWN
    return max(known, key=lambda s: SEVERITY[s])


def aggregate_checks(checks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_id: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
    for c in checks:
        by_id.setdefault(c["id"], []).append(c)
    out = []
    for cid, items in by_id.items():
        st = worst([i["status"] for i in items])
        bad_nodes = [i["node"] for i in items if i["status"] in (FAIL, WARN)]
        rep = next((i for i in items if i["status"] == st), items[0])
        # For criteria scoring, a check that fails on some nodes but passes on
        # others is partial evidence, not a cluster-wide gap.
        mixed = st == FAIL and any(i["status"] in (PASS, NA) for i in items)
        out.append({
            "id": cid,
            "title": rep["title"],
            "status": st,
            "score_status": WARN if mixed else st,
            "criteria": sorted({c for i in items for c in i["criteria"]}),
            "nodes_total": len(items),
            "nodes_affected": bad_nodes,
            "reason": rep["reason"],
            "fix": rep["fix"],
            "source": rep["source"],
        })
    return out


def criterion_status(checks: List[Dict[str, Any]]) -> str:
    sts = [c.get("score_status", c["status"]) for c in checks if c["status"] != UNKNOWN]
    if not sts:
        return UNK
    if all(s in (PASS, NA) for s in sts):
        return MEETS
    if all(s == FAIL for s in sts):
        return GAP
    return PARTIAL


def score(agg: List[Dict[str, Any]], answers: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    criteria = load_criteria()
    by_crit: Dict[str, List[Dict[str, Any]]] = {}
    for c in agg:
        for cid in c["criteria"]:
            by_crit.setdefault(cid, []).append(c)
    rows = []
    for cr in criteria:
        ev = by_crit.get(cr["id"], [])
        st = criterion_status(ev)
        basis = "measured" if st != UNK else ("unmeasured" if ev else "not node-observable")
        note = ""
        if st == UNK and ev:
            note = "; ".join(sorted({e["reason"] for e in ev if e["reason"]}))[:300]
        elif st == UNK:
            note = "Not observable from a node (policy, commercial or provider-level). Record it with --answers."
        else:
            bad = [e for e in ev if e["status"] in (FAIL, WARN)]
            note = "; ".join(f"{e['title']}: {e['reason']}" for e in bad)[:400] if bad else "; ".join(e["title"] for e in ev)[:300]
        if st == UNK and answers and cr["id"] in answers:
            a = answers[cr["id"]]
            if a.get("status") in STATUSES:
                st, basis = a["status"], "self-attested"
                note = (a.get("evidence") or a.get("note") or "")[:300]
        rows.append({
            "id": cr["id"],
            "category": cr["category"],
            "criterion": cr["criterion"],
            "status": st,
            "basis": basis,
            "checks": [e["id"] for e in ev],
            "note": note,
        })

    def idx(rs: List[Dict[str, Any]]) -> float:
        if not rs:
            return 0.0
        return round(100.0 * sum(1.0 if r["status"] == MEETS else 0.5 if r["status"] == PARTIAL else 0.0 for r in rs) / len(rs), 1)

    cats: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
    for r in rows:
        cats.setdefault(r["category"], []).append(r)
    categories = []
    for name, rs in cats.items():
        counts = {s: sum(1 for r in rs if r["status"] == s) for s in STATUSES}
        assessed = [r for r in rs if r["status"] != UNK]
        categories.append({"name": name, "rows": len(rs), "counts": counts, "index": idx(rs), "assessed_index": idx(assessed) if assessed else None})
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in STATUSES}
    assessed = [r for r in rows if r["status"] != UNK]
    return {
        "rows": rows,
        "categories": categories,
        "counts": counts,
        "total": len(rows),
        "index": idx(rows),
        "assessed": len(assessed),
        "assessed_index": idx(assessed) if assessed else None,
    }


def top_fixes(agg: List[Dict[str, Any]], raw: Optional[List[Dict[str, Any]]] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Rank fixes. Nodes that should not take jobs come first as one item;
    then systemic fixes by severity and the number of criteria they move."""
    out: List[Dict[str, Any]] = []
    seen = set()
    bad_health = [c for c in (raw or []) if c["id"] in HEALTH_IDS and c["status"] == FAIL]
    bad_health.sort(key=lambda c: HEALTH_PRIORITY.index(c["id"]) if c["id"] in HEALTH_PRIORITY else 99)
    if bad_health:
        per_node: "OrderedDict[str, List[str]]" = OrderedDict()
        for c in bad_health:
            per_node.setdefault(c["node"], []).append(c["reason"] or c["title"])
        detail = " | ".join(f"{n}: " + "; ".join(r[:110] for r in rs[:5]) for n, rs in per_node.items())
        out.append({
            "check": "nodes.failing",
            "title": f"Drain and repair {len(per_node)} failing node(s)",
            "status": FAIL,
            "fix": detail + ". Keep them out of the scheduler until predge-ready health passes.",
            "criteria": sorted({x for c in bad_health for x in c["criteria"]}),
            "nodes": list(per_node),
        })
        seen.update(c["id"] for c in bad_health)
    cand = [c for c in agg if c["status"] in (FAIL, WARN) and c["fix"] and c["id"] not in seen]

    def weight(c: Dict[str, Any]) -> float:
        return (3.0 if c["status"] == FAIL else 1.0) * (1 + min(len(c["criteria"]), 3)) + 0.1 * len(c["nodes_affected"])

    cand.sort(key=lambda c: (-weight(c), c["id"]))
    fixes = set()
    for c in cand:
        if len(out) >= limit:
            break
        if c["fix"] in fixes:
            continue
        fixes.add(c["fix"])
        out.append({"check": c["id"], "title": c["title"], "status": c["status"], "fix": c["fix"], "criteria": c["criteria"], "nodes": c["nodes_affected"]})
    return out
