"""Optional bridge to SemiAnalysis' ``cmax`` CLI (package ``clustermax``).

If ``cmax`` is installed, ``predge-ready scan --cmax`` runs ``cmax audit`` and
folds its pass/warning/fail/skipped checks into the readiness report, mapped
to the same criteria rows. No cmax code is copied or vendored: we call the
installed CLI and read its result with its own Python interpreter.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .checks import FAIL, PASS, UNKNOWN, WARN, mk

STATUS = {"pass": PASS, "warning": WARN, "fail": FAIL, "skipped": UNKNOWN}

# cmax check key (prefix) -> Predge criteria IDs. Our own mapping, written
# against the public criteria wording.
KEY_MAP: List[Tuple[str, List[str]]] = [
    ("securityVersions.nvidiaContainerToolkit", ["SEC-15", "SEC-16"]),
    ("securityVersions.virtioNetBluefield.exposure", ["SEC-13"]),
    ("securityVersions.dpuHostIsolation", ["SEC-13"]),
    ("securityVersions.", ["SEC-17"]),
    ("security.januscape", ["SEC-14"]),
    ("security.", ["SEC-17"]),
    ("ufm-profile", ["SEC-12"]),
    ("bmc-ipmi", ["SEC-13"]),
    ("pcie-passthrough", ["SEC-13"]),
    ("nvlink-boundary", ["SEC-13"]),
    ("kubernetes-nodes-proxy", ["SEC-13"]),
    ("ingress-nginx", ["SEC-13"]),
    ("observability-isolation", ["SEC-13"]),
    ("qemu-virtio-serial", ["SEC-14"]),
    ("vmscape", ["SEC-14"]),
    ("kubelet_cpu_manager_policy", ["SEC-13"]),
    ("gpus.gdrcopy", ["LIF-8"]),
    ("gpus.gpuDirectRdmaPath", ["LIF-8"]),
    ("gpus.pcieAcs", ["LIF-8"]),
    ("tenant_pod_defaults.checks.rdmaDevices", ["LIF-8"]),
    ("tenant_pod_defaults.checks.gdrcopyDevice", ["LIF-8"]),
    ("containers.nvidiaContainerToolkit", ["LIF-9"]),
    ("software.nvhpc", ["LIF-9"]),
    ("containers.pyxisRuntimeWorks", ["SLU-7"]),
    ("containers.enroot", ["SLU-7"]),
    ("software.ncu", ["MON-1"]),
    ("software.lmod", ["SLU-6"]),
    ("software.cudaVisibleDevicesStatus", ["ORC-6"]),
    ("nccl_topo_file", ["NET-1"]),
    ("networking.topologyConfigured", ["SLU-5", "NET-1"]),
    ("networking.ncclAutoConfig", ["NET-5"]),
    ("storage.rwxStatus", ["STO-3"]),
    ("healthChecks.nhcInstalled", ["MON-3"]),
    ("healthChecks.monitoringStack.dcgmExporter", ["MON-2"]),
    ("healthChecks.dcgmInstalled", ["MON-16"]),
    ("healthChecks.dcgmSlurm", ["MON-16"]),
    ("access.userManagement", ["ORC-1"]),
    ("access.sshToComputeNodes", ["ORC-3"]),
    ("access.externalIdp", ["ORC-2"]),
    ("slurm.accounting.sacctAvailable", ["MON-15"]),
]

_EVAL = r"""
import json, sys
from pathlib import Path
from cmax import audit_report, security
values = json.loads(Path(sys.argv[1]).read_text())
root = security.find_runtime_root(None)
out = []
for c in audit_report.evaluate(values, root):
    out.append({"key": c.key, "title": c.title, "category": c.category, "status": c.status,
                "assessment": c.assessment, "recommendation": c.recommendation})
print(json.dumps(out))
"""


def criteria_for(key: str) -> List[str]:
    for prefix, ids in KEY_MAP:
        if key == prefix or key.startswith(prefix):
            return ids
    return []


def cmax_python() -> Optional[str]:
    exe = shutil.which("cmax")
    if not exe:
        return None
    try:
        with open(exe, "r", errors="replace") as fh:
            first = fh.readline().strip()
    except OSError:
        return None
    if first.startswith("#!"):
        interp = first[2:].strip().split()[0]
        if os.path.exists(interp):
            return interp
    return None


def evaluate_values(values_path: Path) -> List[Dict[str, Any]]:
    py = cmax_python()
    if not py:
        raise RuntimeError("cmax is not installed (pipx install clustermax)")
    proc = subprocess.run([py, "-c", _EVAL, str(values_path)], capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError("cmax evaluation failed: " + (proc.stderr.strip().splitlines() or ["?"])[-1])
    return json.loads(proc.stdout)


def to_checks(items: List[Dict[str, Any]], node: str = "cluster") -> List[Dict[str, Any]]:
    out = []
    for it in items:
        st = STATUS.get(it.get("status", ""), UNKNOWN)
        c = mk("cmax." + it["key"], it.get("title") or it["key"], st, None,
               it.get("assessment", "")[:300], it.get("recommendation", "")[:300], criteria_for(it["key"]), source="cmax")
        c["node"] = node
        out.append(c)
    return out


def run_audit(harness: Optional[str] = None, timeout: int = 1800) -> Tuple[List[Dict[str, Any]], str]:
    """Run ``cmax audit`` and return (checks, note). Never raises."""
    if not shutil.which("cmax"):
        return [], "cmax not installed; skipped (pipx install clustermax to merge its 74 audit checks)"
    root = Path(tempfile.mkdtemp(prefix="predge-cmax-"))
    argv = ["cmax", "audit", "--yes", "--allow-cluster-node"]
    if harness:
        argv.insert(2, f"--{harness}")
    env = dict(os.environ, CLUSTERMAX_RUNS_ROOT=str(root))
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return [], "cmax audit timed out"
    found = sorted(root.rglob("audit.values.json"))
    if not found:
        tail = (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ["no output"]
        return [], f"cmax audit produced no results (exit {proc.returncode}: {tail[0][:200]})"
    try:
        items = evaluate_values(found[-1])
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        return [], str(exc)
    return to_checks(items), f"merged {len(items)} cmax audit checks from {found[-1]}"


def load_results(path: str) -> Tuple[List[Dict[str, Any]], str]:
    """Import an existing cmax audit (directory, audit.values.json, or a JSON list we exported)."""
    p = Path(path)
    if p.is_dir():
        hits = sorted(p.rglob("audit.values.json"))
        if not hits:
            return [], f"no audit.values.json under {p}"
        p = hits[-1]
    data = json.loads(p.read_text())
    if isinstance(data, list):
        return to_checks(data), f"merged {len(data)} cmax checks from {p}"
    items = evaluate_values(p)
    return to_checks(items), f"merged {len(items)} cmax checks from {p}"
