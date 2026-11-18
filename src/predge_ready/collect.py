"""Collect raw facts from one node through a Runner. Read-only; no root needed.

Every section records either data or a ``reason`` explaining why the data is
missing (tool not installed, permission denied, timeout). Checks turn those
reasons into Unknown results instead of guessing.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from . import parsers as P
from .runner import Result, Runner

PARALLEL_FS = {"lustre", "wekafs", "gpfs", "beegfs", "fuse.beegfs", "pvfs2", "orangefs", "panfs", "dvs", "exa", "fuse.weka"}
NETWORK_FS = {"nfs", "nfs4", "cephfs", "ceph", "fuse.cephfs", "glusterfs", "fuse.glusterfs", "fuse.juicefs", "cifs", "smb3", "9p", "virtiofs", "fuse.s3fs", "fuse.mountpoint-s3", "fuse.gcsfuse"}
MONITORING_AGENTS = {
    "dcgm-exporter": "dcgm-exporter",
    "nv-hostengine": "nv-hostengine",
    "node_exporter": "node-exporter",
    "node-exporter": "node-exporter",
    "ipmi_exporter": "ipmi-exporter",
    "ipmi-exporter": "ipmi-exporter",
    "promtail": "promtail",
    "fluent-bit": "fluent-bit",
    "alloy": "grafana-alloy",
    "grafana-agent": "grafana-agent",
    "gpud": "gpud",
    "node-problem-detector": "node-problem-detector",
    "nvsentinel": "nvsentinel",
    "slurmd": "slurmd",
    "kubelet": "kubelet",
    "nvidia-persistenced": "nvidia-persistenced",
}


def _why(res: Result, tool: str) -> str:
    if res.missing:
        return f"{tool} not installed or not on PATH"
    if res.timed_out:
        return f"{tool} timed out"
    msg = (res.err or res.out or "").strip().splitlines()
    tail = msg[-1][:160] if msg else ""
    if "permitted" in tail.lower() or "permission" in tail.lower():
        return f"{tool}: permission denied (run as root or grant read access)"
    return f"{tool} exited {res.rc}: {tail}" if tail else f"{tool} exited {res.rc}"


def collect_gpu(r: Runner) -> Dict[str, Any]:
    fields = P.GPU_BASE_FIELDS + P.GPU_EXTRA_FIELDS
    res = r.run("gpu_query", ["nvidia-smi", f"--query-gpu={','.join(fields)}", "--format=csv,noheader,nounits"], 30)
    if res.missing:
        return {"available": False, "reason": "nvidia-smi not installed (no NVIDIA driver, or not an NVIDIA node)"}
    rows: List[Dict[str, str]] = []
    if res.ok:
        rows = P.parse_gpu_csv(res.out, fields)
    else:
        # Older drivers reject newer fields: fall back field group by field group.
        base = r.run("gpu_query_base", ["nvidia-smi", f"--query-gpu={','.join(P.GPU_BASE_FIELDS)}", "--format=csv,noheader,nounits"], 30)
        if not base.ok:
            return {"available": False, "reason": _why(base, "nvidia-smi")}
        rows = P.parse_gpu_csv(base.out, P.GPU_BASE_FIELDS)
        for extra in P.GPU_EXTRA_FIELDS + [P.GPU_LEGACY_THROTTLE_FIELD]:
            key = "gpu_query_" + extra.replace(".", "_")
            ex = r.run(key, ["nvidia-smi", f"--query-gpu={extra}", "--format=csv,noheader,nounits"], 20)
            if ex.ok:
                vals = [v.strip() for v in ex.out.strip().splitlines()]
                for row, v in zip(rows, vals):
                    row[extra] = v
    gpus = [P.normalize_gpu(x) for x in rows]
    out: Dict[str, Any] = {"available": True, "gpus": gpus, "count": len(gpus)}
    out["driver"] = gpus[0]["driver"] if gpus else None
    smi = r.run("nvidia_smi", ["nvidia-smi"], 30)
    out["cuda"] = P.parse_cuda_version(smi.out) if smi.ok else None
    ver = r.read("/proc/driver/nvidia/version")
    out["open_kernel_module"] = None if ver is None else ("Open Kernel Module" in ver)
    params = r.read("/proc/driver/nvidia/params")
    out["params"] = P.parse_nvidia_params(params) if params is not None else None
    return out


def collect(r: Runner, active: bool = False, active_opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    f: Dict[str, Any] = {"host": r.host, "is_root": r.is_root()}
    h = r.run("hostname", ["hostname", "-s"], 5)
    if h.ok and h.out.strip():
        f["host"] = h.out.strip()
    u = r.run("uname", ["uname", "-r"], 5)
    f["kernel"] = u.out.strip() if u.ok else None
    osr = r.read("/etc/os-release") or ""
    m = re.search(r'^PRETTY_NAME="?([^"\n]+)', osr, re.M)
    f["os"] = m.group(1) if m else None

    f["gpu"] = collect_gpu(r)

    lspci = r.run("lspci_nvidia", ["lspci", "-d", "10de:", "-nn"], 15)
    f["lspci_gpu_count"] = P.count_lspci_gpus(lspci.out) if lspci.ok else None
    f["lspci_reason"] = None if lspci.ok else _why(lspci, "lspci")

    if f["gpu"].get("available"):
        nv = r.run("nvlink", ["nvidia-smi", "nvlink", "-s"], 20)
        f["nvlink"] = P.parse_nvlink_status(nv.out) if nv.ok else {"reason": _why(nv, "nvidia-smi nvlink")}
        fm = r.run("fabricmanager", ["systemctl", "is-active", "nvidia-fabricmanager"], 5)
        f["fabricmanager"] = (fm.out.strip() or fm.err.strip() or None) if not fm.missing else None
    else:
        f["nvlink"] = {"reason": "no NVIDIA GPUs visible"}
        f["fabricmanager"] = None

    # Kernel log for XID / SXID. dmesg is often restricted for non-root users.
    xsrc, xtext, xreason = None, None, None
    d = r.run("dmesg", ["dmesg"], 15)
    if d.ok and d.out:
        xsrc, xtext = "dmesg", d.out
    else:
        j = r.run("journal_kernel", ["journalctl", "-k", "-b", "0", "--no-pager", "-q"], 20)
        if j.ok and j.out:
            xsrc, xtext = "journalctl -k -b 0", j.out
        else:
            xreason = "kernel log not readable: " + _why(d, "dmesg") + "; " + _why(j, "journalctl")
    if xtext is not None:
        xids, sxids = P.parse_xids(xtext)
        f["xid"] = {"source": xsrc, "events": xids, "sxid": sxids}
    else:
        f["xid"] = {"reason": xreason}

    ib = r.run("ibstat", ["ibstat"], 15)
    if ib.ok:
        ports = P.parse_ibstat(ib.out)
        f["ib"] = {"ports": ports}
        pk = r.run("pkeys", ["sh", "-c", "grep -H . /sys/class/infiniband/*/ports/*/pkeys/* 2>/dev/null | grep -v ':0x0000$'"], 15)
        pkeys: Dict[str, List[str]] = {}
        if pk.ok or pk.out:
            for line in pk.out.splitlines():
                mm = re.search(r"/sys/class/infiniband/([^/]+)/ports/(\d+)/pkeys/\d+:(0x[0-9a-fA-F]+)", line)
                if mm:
                    pkeys.setdefault(f"{mm.group(1)}/{mm.group(2)}", []).append(mm.group(3).lower())
        f["ib"]["pkeys"] = {k: sorted(set(v)) for k, v in pkeys.items()} or None
    else:
        devs = r.listdir("/sys/class/infiniband")
        f["ib"] = {"reason": _why(ib, "ibstat"), "devices": devs}

    mods = r.read("/proc/modules")
    f["modules"] = P.parse_modules(mods) if mods is not None else None

    acs = r.run("lspci_acs", ["lspci", "-vvv"], 30)
    if acs.ok:
        parsed = P.parse_acs(acs.out)
        if parsed["access_denied"] and not parsed["acs_capable_ports"]:
            f["acs"] = {"reason": "lspci capabilities need root (run the scan with sudo for this check)"}
        else:
            f["acs"] = parsed
    else:
        f["acs"] = {"reason": _why(acs, "lspci")}

    f["containers"] = collect_containers(r)
    f["slurm"] = collect_slurm(r, f["host"])
    f["k8s"] = collect_k8s(r)

    mounts_text = r.read("/proc/mounts")
    if mounts_text is not None:
        mounts = P.parse_mounts(mounts_text)
        shared = [m for m in mounts if m["fstype"] in PARALLEL_FS or m["fstype"] in NETWORK_FS]
        f["mounts"] = {"shared": shared}
        if shared:
            st = r.run("statfs", ["stat", "-f", shared[0]["mountpoint"]], 8)
            f["mounts"]["responsive"] = st.ok
            f["mounts"]["probe"] = shared[0]["mountpoint"]
    else:
        f["mounts"] = {"reason": "/proc/mounts not readable"}

    ps = r.run("ps", ["ps", "-eo", "comm=,args="], 10)
    if ps.ok:
        found = set()
        for line in ps.out.splitlines():
            low = line.lower()
            for needle, name in MONITORING_AGENTS.items():
                if needle in low:
                    found.add(name)
        f["agents"] = sorted(found)
    else:
        f["agents"] = None
    units = r.run("units", ["systemctl", "list-units", "--type=service,timer", "--no-legend", "--plain", "--all"], 10)
    f["units"] = [ln.split()[0] for ln in units.out.splitlines() if ln.strip()] if units.ok else None

    f["nccl_conf"] = r.read("/etc/nccl.conf")
    f["perf_event_paranoid"] = (r.read("/proc/sys/kernel/perf_event_paranoid") or "").strip() or None
    f["kptr_restrict"] = (r.read("/proc/sys/kernel/kptr_restrict") or "").strip() or None

    sw: Dict[str, Any] = {}
    nvcc = r.run("nvcc", ["nvcc", "--version"], 10)
    if nvcc.missing:
        nvcc = r.run("nvcc", ["/usr/local/cuda/bin/nvcc", "--version"], 10)
    mm = re.search(r"release ([0-9.]+)", nvcc.out) if nvcc.ok else None
    sw["nvcc"] = mm.group(1) if mm else None
    sw["hpcx"] = r.listdir("/opt/hpcx") is not None or r.which("/opt/hpcx")
    sw["lmod"] = any(r.listdir(p) is not None for p in ("/usr/share/lmod", "/opt/apps/lmod", "/usr/share/lmod/lmod"))
    ld = r.run("ldconfig", ["ldconfig", "-p"], 10)
    if ld.ok:
        sw["nccl_lib"] = "libnccl.so" in ld.out
        sw["gdrapi_lib"] = "libgdrapi.so" in ld.out
    dv = r.run("dcgmi_version", ["dcgmi", "--version"], 10)
    mm = re.search(r"[Vv]ersion\s*:?\s*([0-9.]+)", dv.out) if dv.ok else None
    sw["dcgm"] = mm.group(1) if mm else (None if dv.missing else "unknown")
    f["software"] = sw

    if active:
        from .active import run_active

        f["active"] = run_active(r, f, active_opts or {})
    return f


def collect_containers(r: Runner) -> Dict[str, Any]:
    c: Dict[str, Any] = {}
    for key, argv, rx in (
        ("docker", ["docker", "--version"], r"version ([0-9.]+)"),
        ("nvidia_ctk", ["nvidia-ctk", "--version"], r"version ([0-9.]+)"),
        ("nvidia_container_cli", ["nvidia-container-cli", "--version"], r"(?:cli-)?version:?\s*([0-9.]+)"),
        ("enroot", ["enroot", "version"], r"([0-9]+\.[0-9.]+)"),
        ("apptainer", ["apptainer", "--version"], r"([0-9]+\.[0-9.]+)"),
        ("singularity", ["singularity", "--version"], r"([0-9]+\.[0-9.]+)"),
    ):
        res = r.run(key, argv, 10)
        if res.ok:
            mm = re.search(rx, res.out, re.I)
            c[key] = mm.group(1) if mm else "present"
        else:
            c[key] = None
    plug = r.run("plugstack", ["sh", "-c", "cat /etc/slurm/plugstack.conf /etc/slurm/plugstack.conf.d/* /etc/slurm-llnl/plugstack.conf 2>/dev/null"], 10)
    c["pyxis"] = ("pyxis" in plug.out) if (plug.ok or plug.out) else None
    return c


def collect_slurm(r: Runner, host: str) -> Dict[str, Any]:
    s: Dict[str, Any] = {"present": r.which("scontrol") or r.which("slurmd") or r.which("sinfo")}
    if not s["present"]:
        return s
    cfg = r.run("scontrol_config", ["scontrol", "show", "config"], 15)
    if cfg.ok:
        c = P.parse_kv_config(cfg.out)
        keep = (
            "ClusterName", "SLURM_VERSION", "HealthCheckProgram", "HealthCheckInterval", "HealthCheckNodeState",
            "TopologyPlugin", "TopologyParam", "Prolog", "Epilog", "PrologFlags", "PlugStackConfig", "SelectType",
            "SelectTypeParameters", "GresTypes", "AccountingStorageType", "JobAcctGatherType", "MpiDefault",
            "DefMemPerCPU", "DefMemPerGPU", "DefCpuPerGPU", "ProctrackType", "TaskPlugin",
        )
        s["config"] = {k: c[k] for k in keep if k in c}
    else:
        s["reason"] = _why(cfg, "scontrol show config")
    node = r.run("scontrol_node", ["scontrol", "show", "node", host], 10)
    if node.ok:
        mm = re.search(r"State=(\S+)", node.out)
        s["node_state"] = mm.group(1) if mm else None
        mm = re.search(r"Reason=(.*?)(?: \[|$)", node.out, re.M)
        s["node_reason"] = mm.group(1).strip() if mm else None
        mm = re.search(r"Gres=(\S+)", node.out)
        s["node_gres"] = mm.group(1) if mm else None
    return s


def collect_k8s(r: Runner) -> Dict[str, Any]:
    k: Dict[str, Any] = {"kubelet": r.which("kubelet") or r.listdir("/var/lib/kubelet") is not None, "kubectl": r.which("kubectl")}
    if not k["kubectl"]:
        return k
    nodes = r.run("kubectl_nodes", ["kubectl", "get", "nodes", "-o", "name"], 15)
    k["api_ok"] = nodes.ok
    if not nodes.ok:
        k["reason"] = _why(nodes, "kubectl get nodes")
        return k
    k["nodes"] = len(nodes.out.split())
    sc = r.run("kubectl_sc", ["kubectl", "get", "storageclass", "-o", "json"], 15)
    if sc.ok:
        try:
            items = json.loads(sc.out).get("items", [])
            k["storageclasses"] = [
                {
                    "name": i["metadata"]["name"],
                    "provisioner": i.get("provisioner", ""),
                    "default": i["metadata"].get("annotations", {}).get("storageclass.kubernetes.io/is-default-class") == "true",
                }
                for i in items
            ]
        except (ValueError, KeyError):
            k["storageclasses"] = None
    pods = r.run("kubectl_pods", ["kubectl", "get", "pods", "-A", "-o", "name"], 20)
    if pods.ok:
        names = pods.out.lower()
        k["operators"] = {
            "gpu-operator": "gpu-operator" in names,
            "network-operator": "network-operator" in names,
            "mpi-operator": "mpi-operator" in names,
            "dcgm-exporter": "dcgm-exporter" in names,
            "kube-prometheus-stack": "prometheus" in names,
            "node-problem-detector": "node-problem-detector" in names,
        }
    return k
