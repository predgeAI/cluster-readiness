"""Fast node health check for Slurm HealthCheckProgram, cron or a systemd timer.

Exit codes:
  0  healthy
  1  warning (degraded, keep scheduling but look at it)
  2  failing (should not take jobs; drained when --drain is given)
  3  could not check (no GPU tooling, or an internal error)
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import parsers as P
from .checks import FAIL, HEALTH_PRIORITY, PASS, UNKNOWN, WARN, mk, node_checks
from .collect import _why, collect_gpu
from .runner import Runner

HEALTH_CHECK_IDS = (
    "gpu.count", "gpu.model", "gpu.throttle", "gpu.temperature", "gpu.ecc", "gpu.row_remap", "gpu.pcie_link",
    "gpu.nvlink", "gpu.fabricmanager", "gpu.xid", "ib.ports_up",
)
REASON_PREFIX = "predge-ready:"
EXIT = {"healthy": 0, "warning": 1, "failing": 2, "unknown": 3}


def collect_fast(r: Runner) -> Dict[str, Any]:
    f: Dict[str, Any] = {"host": r.host}
    h = r.run("hostname", ["hostname", "-s"], 5)
    if h.ok and h.out.strip():
        f["host"] = h.out.strip()
    f["gpu"] = collect_gpu(r)
    lspci = r.run("lspci_nvidia", ["lspci", "-d", "10de:", "-nn"], 10)
    f["lspci_gpu_count"] = P.count_lspci_gpus(lspci.out) if lspci.ok else None
    if f["gpu"].get("available"):
        nv = r.run("nvlink", ["nvidia-smi", "nvlink", "-s"], 15)
        f["nvlink"] = P.parse_nvlink_status(nv.out) if nv.ok else {"reason": _why(nv, "nvidia-smi nvlink")}
        fm = r.run("fabricmanager", ["systemctl", "is-active", "nvidia-fabricmanager"], 5)
        f["fabricmanager"] = (fm.out.strip() or fm.err.strip() or None) if not fm.missing else None
    else:
        f["nvlink"] = {"reason": "no NVIDIA GPUs visible"}
    d = r.run("dmesg", ["dmesg"], 10)
    text = d.out if d.ok and d.out else None
    src = "dmesg"
    if text is None:
        j = r.run("journal_kernel", ["journalctl", "-k", "-b", "0", "--no-pager", "-q"], 15)
        text, src = (j.out, "journalctl -k -b 0") if j.ok and j.out else (None, None)
    if text is None:
        f["xid"] = {"reason": "kernel log not readable (run as root, e.g. from slurmd or a root systemd unit)"}
    else:
        x, s = P.parse_xids(text)
        f["xid"] = {"source": src, "events": x, "sxid": s}
    ib = r.run("ibstat", ["ibstat"], 10)
    f["ib"] = {"ports": P.parse_ibstat(ib.out)} if ib.ok else {"reason": _why(ib, "ibstat"), "devices": r.listdir("/sys/class/infiniband")}
    return f


def quick_nccl(r: Runner, ngpu: int, floor: Optional[float], binary: str = "all_reduce_perf") -> Dict[str, Any]:
    res = r.run("nccl_quick", [binary, "-b", "1G", "-e", "1G", "-n", "10", "-w", "2", "-g", str(ngpu)], 90)
    if res.missing:
        return mk("health.nccl_quick", "Quick NCCL all_reduce", UNKNOWN, None, "all_reduce_perf not found")
    bw = P.parse_nccl_tests(res.out)
    if bw is None:
        return mk("health.nccl_quick", "Quick NCCL all_reduce", FAIL if res.rc else UNKNOWN, None, f"all_reduce_perf exited {res.rc}",
                  "Run nccl-tests by hand on this node.")
    st = FAIL if floor and bw < floor else PASS
    return mk("health.nccl_quick", "Quick NCCL all_reduce", st, {"busbw_gbs": bw, "floor_gbs": floor},
              f"{bw} GB/s below {floor} GB/s" if st == FAIL else "", "Drain and run dcgmi diag -r 3.")


def evaluate(r: Runner, expect: Dict[str, str], thr: Dict[str, float], mins: Dict[str, Any], nccl: bool = False,
             nccl_floor: Optional[float] = None, nccl_bin: str = "all_reduce_perf") -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    facts = collect_fast(r)
    checks = [c for c in node_checks(facts, expect, thr, mins) if c["id"] in HEALTH_CHECK_IDS]
    gpus = (facts.get("gpu") or {}).get("gpus") or []
    if nccl and gpus:
        c = quick_nccl(r, len(gpus), nccl_floor, nccl_bin)
        c["node"] = facts["host"]
        checks.append(c)
    sts = [c["status"] for c in checks]
    if FAIL in sts:
        state = "failing"
    elif not facts["gpu"].get("available") and not facts.get("lspci_gpu_count"):
        state = "unknown"
    elif WARN in sts:
        state = "warning"
    else:
        state = "healthy"
    return state, checks, facts


SHORT = {
    "gpu.ecc": "uncorrectable ECC", "gpu.row_remap": "row remap failed", "ib.ports_up": "IB port down",
    "gpu.nvlink": "NVLink down", "gpu.throttle": "HW clock throttling", "gpu.temperature": "GPU overtemp",
    "gpu.model": "wrong GPU model", "gpu.pcie_link": "PCIe link degraded", "gpu.fabricmanager": "fabric manager down",
    "health.nccl_quick": "NCCL bandwidth low",
}


def short_label(c: Dict[str, Any]) -> str:
    obs = c.get("observed") or {}
    if c["id"] == "gpu.count" and isinstance(obs, dict) and obs.get("nvidia_smi") is not None:
        want = max(x for x in (obs.get("expected"), obs.get("lspci"), 0) if x is not None)
        return f"GPU missing ({obs['nvidia_smi']}/{want})"
    if c["id"] == "gpu.count":
        return "GPU driver not responding"
    if c["id"] == "gpu.xid" and isinstance(obs, dict):
        return "XID " + ",".join(str(x) for x in obs.get("xid_codes", []))
    return SHORT.get(c["id"], c["title"])


def drain_reason(checks: List[Dict[str, Any]]) -> str:
    bad = sorted((c for c in checks if c["status"] == FAIL),
                 key=lambda c: HEALTH_PRIORITY.index(c["id"]) if c["id"] in HEALTH_PRIORITY else 99)
    parts = [short_label(c) for c in bad[:5]]
    reason = f"{REASON_PREFIX} " + ", ".join(parts)
    return reason[:200]


def detect_mode(which: Callable[[str], bool]) -> Optional[str]:
    if which("scontrol") and (which("slurmd") or os.environ.get("SLURMD_NODENAME")):
        return "slurm"
    if which("kubectl"):
        return "k8s"
    if which("scontrol"):
        return "slurm"
    return None


Exec = Callable[[List[str]], Tuple[int, str]]


def _exec(argv: List[str]) -> Tuple[int, str]:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def slurm_state(node: str, run: Exec) -> Tuple[str, str]:
    rc, out = run(["scontrol", "show", "node", node])
    if rc != 0:
        return "", ""
    m = re.search(r"State=(\S+)", out)
    r = re.search(r"Reason=(.*?)(?: \[|$)", out, re.M)
    return (m.group(1) if m else ""), (r.group(1).strip() if r else "")


def act(state: str, checks: List[Dict[str, Any]], *, mode: str, node: str, drain: bool, resume: bool, dry_run: bool,
        run: Exec = _exec) -> List[str]:
    """Drain on failure; optionally resume a node this tool drained once it is healthy again."""
    log: List[str] = []
    cmds: List[List[str]] = []
    if mode == "slurm":
        cur, cur_reason = slurm_state(node, run) if not dry_run else ("", "")
        drained = "DRAIN" in cur.upper()
        if state == "failing" and drain:
            if drained:
                log.append(f"{node} already drained ({cur_reason or cur}); leaving it")
            else:
                cmds.append(["scontrol", "update", f"nodename={node}", "state=drain", f"reason={drain_reason(checks)}"])
        elif state == "healthy" and resume and drained and cur_reason.startswith(REASON_PREFIX):
            cmds.append(["scontrol", "update", f"nodename={node}", "state=resume"])
    elif mode == "k8s":
        if state == "failing" and drain:
            cmds.append(["kubectl", "cordon", node])
            cmds.append(["kubectl", "annotate", "node", node, "--overwrite", f"predge.io/health={drain_reason(checks)}"])
        elif state == "healthy" and resume:
            rc, out = run(["kubectl", "get", "node", node, "-o", "jsonpath={.metadata.annotations.predge\\.io/health}"]) if not dry_run else (1, "")
            if rc == 0 and out.startswith(REASON_PREFIX):
                cmds.append(["kubectl", "uncordon", node])
                cmds.append(["kubectl", "annotate", "node", node, "predge.io/health-"])
    elif drain and state == "failing":
        log.append("no scheduler found (scontrol or kubectl); nothing drained")
    for c in cmds:
        if dry_run:
            log.append("would run: " + " ".join(_q(a) for a in c))
        else:
            rc, out = run(c)
            log.append(("ran: " if rc == 0 else f"FAILED ({rc}): ") + " ".join(_q(a) for a in c) + (f" -> {out}" if out and rc else ""))
    return log


def _q(a: str) -> str:
    return a if re.match(r"^[\w./=:,@-]+$", a) else "'" + a.replace("'", "'\\''") + "'"


def prometheus(node: str, state: str, checks: List[Dict[str, Any]], facts: Dict[str, Any], duration: float) -> str:
    code = {PASS: 0, "na": 0, WARN: 1, FAIL: 2, UNKNOWN: 3}
    L = [
        "# HELP predge_ready_health_status Node health: 0 healthy, 1 warning, 2 failing, 3 unknown.",
        "# TYPE predge_ready_health_status gauge",
        f'predge_ready_health_status{{node="{node}"}} {EXIT[state]}',
        "# HELP predge_ready_check_status Per-check status: 0 pass, 1 warn, 2 fail, 3 unknown.",
        "# TYPE predge_ready_check_status gauge",
    ]
    for c in checks:
        L.append(f'predge_ready_check_status{{node="{node}",check="{c["id"]}"}} {code.get(c["status"], 3)}')
    gpus = (facts.get("gpu") or {}).get("gpus") or []
    L += ["# HELP predge_ready_gpus_visible GPUs visible to nvidia-smi.", "# TYPE predge_ready_gpus_visible gauge",
          f'predge_ready_gpus_visible{{node="{node}"}} {len(gpus)}']
    if gpus:
        L += ["# HELP predge_ready_gpu_temperature_celsius GPU core temperature.", "# TYPE predge_ready_gpu_temperature_celsius gauge"]
        for g in gpus:
            if g.get("temp_c") is not None:
                L.append(f'predge_ready_gpu_temperature_celsius{{node="{node}",gpu="{g["index"]}"}} {g["temp_c"]:g}')
        L += ["# HELP predge_ready_gpu_ecc_uncorrected Volatile uncorrectable ECC errors.", "# TYPE predge_ready_gpu_ecc_uncorrected gauge"]
        for g in gpus:
            if g.get("ecc_uncorrected") is not None:
                L.append(f'predge_ready_gpu_ecc_uncorrected{{node="{node}",gpu="{g["index"]}"}} {g["ecc_uncorrected"]:g}')
    xids: Dict[int, int] = {}
    for e in ((facts.get("xid") or {}).get("events") or []):
        xids[e["xid"]] = xids.get(e["xid"], 0) + 1
    L += ["# HELP predge_ready_xid_events XID events in the kernel log since boot.", "# TYPE predge_ready_xid_events gauge"]
    for code_, n in sorted(xids.items()):
        L.append(f'predge_ready_xid_events{{node="{node}",xid="{code_}"}} {n}')
    L += ["# HELP predge_ready_last_run_timestamp_seconds Unix time of the last health run.", "# TYPE predge_ready_last_run_timestamp_seconds gauge",
          f'predge_ready_last_run_timestamp_seconds{{node="{node}"}} {int(time.time())}',
          "# HELP predge_ready_run_duration_seconds Duration of the last health run.", "# TYPE predge_ready_run_duration_seconds gauge",
          f'predge_ready_run_duration_seconds{{node="{node}"}} {duration:.3f}']
    return "\n".join(L) + "\n"


def write_textfile(path: str, text: str) -> None:
    """Atomic write for the node_exporter textfile collector."""
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w") as fh:
        fh.write(text)
    os.replace(tmp, path)
