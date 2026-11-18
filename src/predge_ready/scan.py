"""Build a readiness report from one or many nodes."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__
from .checks import FAIL, HEALTH_IDS, UNKNOWN, WARN, cluster_checks, mk, node_checks
from .collect import collect
from .runner import FixtureRunner, Runner, SSHRunner
from .score import aggregate_checks, score, top_fixes


DEMOS = {
    "healthy": ["gpu-h100-01", "gpu-h100-02"],
    "broken": ["gpu-h100-01", "gpu-h100-07", "gpu-a40-03"],
}

DEFAULT_THRESHOLDS = {"temp_warn": 80.0, "temp_fail": 87.0}


def fixture_root() -> Path:
    return Path(str(resources.files("predge_ready").joinpath("fixtures")))


def demo_runners(kind: str) -> List[Runner]:
    if kind not in DEMOS:
        raise ValueError(f"unknown demo '{kind}' (choose: {', '.join(DEMOS)})")
    return [FixtureRunner(fixture_root() / n) for n in DEMOS[kind]]


def node_health(checks: List[Dict[str, Any]]) -> str:
    sts = [c["status"] for c in checks if c["id"] in HEALTH_IDS]
    if FAIL in sts:
        return "failing"
    if WARN in sts:
        return "warning"
    if not [s for s in sts if s != UNKNOWN]:
        return "unknown"
    return "healthy"


def inventory(f: Dict[str, Any]) -> Dict[str, Any]:
    g = f.get("gpu") or {}
    gpus = g.get("gpus") or []
    names: Dict[str, int] = {}
    for x in gpus:
        names[x["name"]] = names.get(x["name"], 0) + 1
    gtxt = ", ".join(f"{n}x {k}" for k, n in names.items()) or (g.get("reason") or "no GPUs")
    ports = (f.get("ib") or {}).get("ports") or []
    fab: Dict[str, int] = {}
    for p in ports:
        if (p.get("rate") or 0) >= 100:
            key = f"{p['link_layer'] or '?'} {int(p['rate'])}G {'up' if p['state'].lower() == 'active' else 'DOWN'}"
            fab[key] = fab.get(key, 0) + 1
    ftxt = ", ".join(f"{n}x {k}" for k, n in sorted(fab.items())) or ((f.get("ib") or {}).get("reason") or "no RDMA ports")
    return {"gpus": gtxt, "driver": g.get("driver"), "cuda": g.get("cuda"), "fabric": ftxt, "os": f.get("os"), "kernel": f.get("kernel")}


def scan_node(r: Runner, expect: Dict[str, str], thr: Dict[str, float], mins: Dict[str, Any], active: bool, active_opts: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(r, SSHRunner):
        ping = r.reachable()
        if ping.rc != 0:
            c = mk("node.reachable", "Node reachable over SSH", FAIL, None, ping.err.strip()[:200] or "ssh failed",
                   "Fix passwordless SSH from the scan host (ClusterMAX expects passwordless SSH between nodes).", ["ORC-3"])
            c["node"] = r.host
            return {"host": r.host, "facts": {"host": r.host}, "checks": [c], "health": "unknown",
                    "inventory": {"gpus": "unreachable", "driver": None, "cuda": None, "fabric": "-", "os": None, "kernel": None}}
    facts = collect(r, active=active, active_opts=active_opts)
    chks = node_checks(facts, expect, thr, mins)
    if isinstance(r, SSHRunner):
        c = mk("node.reachable", "Node reachable over SSH", "pass", None, criteria=["ORC-3"])
        c["node"] = facts["host"]
        chks.append(c)
    return {"host": facts["host"], "facts": facts, "checks": chks, "health": node_health(chks), "inventory": inventory(facts)}


def build_report(
    runners: List[Runner],
    *,
    expect: Optional[Dict[str, str]] = None,
    thresholds: Optional[Dict[str, float]] = None,
    minimums: Dict[str, Any],
    active: bool = False,
    active_opts: Optional[Dict[str, Any]] = None,
    extra_checks: Optional[List[Dict[str, Any]]] = None,
    notes: Optional[List[str]] = None,
    mode: str = "live",
    name: Optional[str] = None,
    answers: Optional[Dict[str, Any]] = None,
    parallel: int = 8,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    expect = expect or {}
    thr = dict(DEFAULT_THRESHOLDS, **(thresholds or {}))
    with ThreadPoolExecutor(max_workers=max(1, parallel)) as ex:
        nodes = list(ex.map(lambda r: scan_node(r, expect, thr, minimums, active, active_opts or {}), runners))
    return assemble(nodes, expect=expect, extra_checks=extra_checks, notes=notes, mode=mode, name=name, answers=answers,
                    generated_at=generated_at, active=active)


def assemble(nodes: List[Dict[str, Any]], *, expect: Dict[str, str], extra_checks: Optional[List[Dict[str, Any]]] = None,
             notes: Optional[List[str]] = None, mode: str = "live", name: Optional[str] = None,
             answers: Optional[Dict[str, Any]] = None, generated_at: Optional[str] = None, active: bool = False) -> Dict[str, Any]:
    all_checks: List[Dict[str, Any]] = [c for n in nodes for c in n["checks"]]
    all_checks += cluster_checks([n for n in nodes if n["facts"].get("gpu")])
    all_checks += extra_checks or []
    agg = aggregate_checks(all_checks)
    sc = score(agg, answers)
    health = {
        "healthy": sum(1 for n in nodes if n["health"] == "healthy"),
        "warning": sum(1 for n in nodes if n["health"] == "warning"),
        "failing": sum(1 for n in nodes if n["health"] == "failing"),
        "unknown": sum(1 for n in nodes if n["health"] == "unknown"),
    }
    cluster_name = name
    if not cluster_name:
        for n in nodes:
            cfg = ((n["facts"].get("slurm") or {}).get("config") or {})
            if cfg.get("ClusterName"):
                cluster_name = cfg["ClusterName"]
                break
    cluster_name = cluster_name or (nodes[0]["host"] if len(nodes) == 1 else "cluster")
    note_list = list(notes or [])
    if nodes and not any((n["facts"].get("gpu") or {}).get("available") for n in nodes):
        note_list.append("No NVIDIA GPUs were found on the scanned host(s). Run the scan on a GPU node, or try --demo to see a sample report.")
    if not active:
        note_list.append("Active tests (dcgmi diag, nccl-tests, ib_write_bw, GEMM) were not run. Add --active on idle or drained nodes.")
    return {
        "schema": "predge-ready/report/v1",
        "tool": {"name": "predge-ready", "version": __version__},
        "generated_at": generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "label": "Independent readiness estimate against published ClusterMAX criteria. Not a SemiAnalysis rating.",
        "mode": mode,
        "cluster": {"name": cluster_name},
        "expect": expect,
        "active_tests": active,
        "health": health,
        "score": sc,
        "top_fixes": top_fixes(agg, all_checks),
        "checks": agg,
        "nodes": [{"host": n["host"], "health": n["health"], "inventory": n["inventory"], "checks": n["checks"], "facts": n["facts"]} for n in nodes],
        "extra_checks": extra_checks or [],
        "notes": note_list,
    }
