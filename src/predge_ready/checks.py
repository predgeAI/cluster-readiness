"""Turn collected facts into checks: pass / warn / fail / na / unknown.

Each check names the ClusterMAX criteria rows it is evidence for (see
data/criteria.json). A check that cannot run reports ``unknown`` with a reason.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any, Dict, List, Optional

from . import parsers as P
from .collect import PARALLEL_FS

PASS, WARN, FAIL, NA, UNKNOWN = "pass", "warn", "fail", "na", "unknown"
SEVERITY = {FAIL: 4, WARN: 3, PASS: 1, NA: 1, UNKNOWN: 0}
# Checks that decide whether a node should take jobs, most urgent first.
HEALTH_PRIORITY = ["gpu.count", "gpu.xid", "gpu.ecc", "gpu.row_remap", "ib.ports_up", "gpu.nvlink", "gpu.throttle", "gpu.temperature",
                   "gpu.model", "gpu.memory", "gpu.pcie_link", "gpu.fabricmanager", "storage.shared_fs", "active.dcgm_diag",
                   "active.nccl", "active.ib_write_bw", "active.gemm", "health.nccl_quick"]
HEALTH_IDS = {
    "gpu.count", "gpu.model", "gpu.memory", "gpu.throttle", "gpu.temperature", "gpu.ecc", "gpu.row_remap", "gpu.pcie_link",
    "gpu.nvlink", "gpu.fabricmanager", "gpu.xid", "ib.ports_up", "storage.shared_fs", "active.dcgm_diag", "active.nccl",
    "active.ib_write_bw", "active.gemm",
}

CURRENT_GEN = ("B200", "B300", "GB200", "GB300", "MI355X", "MI350X")
PREV_GEN = ("H100", "H200", "H800", "H20", "GH200", "MI300X", "MI325X")
CURRENT_MODELS = ("H100", "H200", "A100", "L40S", "MI300X", "B200", "B300", "GB200", "GB300", "GH200", "MI325X", "MI355X", "RTX PRO 6000")


def load_minimums(path: Optional[str] = None) -> Dict[str, Any]:
    if path:
        with open(path) as fh:
            return json.load(fh)
    return json.loads(resources.files("predge_ready").joinpath("data/minimums.json").read_text())


def mk(cid: str, title: str, status: str, observed: Any = None, reason: str = "", fix: str = "", criteria: Optional[List[str]] = None, source: str = "predge") -> Dict[str, Any]:
    return {
        "id": cid,
        "title": title,
        "status": status,
        "observed": observed,
        "reason": reason,
        "fix": fix if status in (FAIL, WARN) else "",
        "criteria": criteria or [],
        "source": source,
    }


def driver_minimum(driver: str, mins: Dict[str, Any]) -> Optional[str]:
    branch = (driver or "").split(".")[0]
    return (mins.get("nvidiaDriverBranches") or {}).get(branch)


def node_checks(f: Dict[str, Any], expect: Dict[str, str], thr: Dict[str, float], mins: Dict[str, Any]) -> List[Dict[str, Any]]:
    C: List[Dict[str, Any]] = []
    g = f.get("gpu") or {}
    gpus = g.get("gpus") or []
    has_gpu = bool(g.get("available")) and bool(gpus)
    noreason = g.get("reason") or "no GPUs reported by nvidia-smi"

    # --- GPU inventory -----------------------------------------------------
    exp_count = int(expect["count"]) if expect.get("count") else None
    lspci = f.get("lspci_gpu_count")
    if not g.get("available"):
        if lspci:
            C.append(mk("gpu.count", "All GPUs visible to the driver", FAIL, {"nvidia_smi": None, "lspci": lspci},
                        f"lspci shows {lspci} NVIDIA GPUs but nvidia-smi failed: {noreason}",
                        "Check the NVIDIA driver (dmesg, nvidia-bug-report.sh); drain the node until it is fixed.", ["REL-4"]))
        else:
            C.append(mk("gpu.count", "All GPUs visible to the driver", UNKNOWN, None, noreason, criteria=["REL-4"]))
    else:
        n = len(gpus)
        want = max(x for x in (exp_count, lspci, 0) if x is not None)
        obs = {"nvidia_smi": n, "lspci": lspci, "expected": exp_count}
        if n < want:
            C.append(mk("gpu.count", "All GPUs visible to the driver", FAIL, obs,
                        f"{n} GPUs visible to nvidia-smi, {want} expected" + (" (lspci sees more: a GPU has likely fallen off the bus)" if lspci and lspci > n else ""),
                        "Drain the node, collect nvidia-bug-report.sh, reseat or RMA the missing GPU.", ["REL-4"]))
        else:
            C.append(mk("gpu.count", "All GPUs visible to the driver", PASS, obs, f"{n} GPUs visible", criteria=["REL-4"]))

    if has_gpu:
        names = sorted({x["name"] for x in gpus})
        mem = sorted({int(x["memory_mib"] or 0) for x in gpus})
        if expect.get("gpu"):
            want = expect["gpu"].lower()
            bad = [x["name"] for x in gpus if want not in x["name"].lower()]
            if bad:
                C.append(mk("gpu.model", "GPU model matches what was sold", FAIL, {"reported": names, "expected": expect["gpu"]},
                            f"Node reports {', '.join(sorted(set(bad)))} but {expect['gpu']} was expected",
                            "Fix the node inventory or the offer: customers are billed for the expected model.", ["LIF-4"]))
            else:
                C.append(mk("gpu.model", "GPU model matches what was sold", PASS, {"reported": names, "expected": expect["gpu"]}, "", criteria=["LIF-4"]))
        else:
            C.append(mk("gpu.model", "GPU model matches what was sold", UNKNOWN, {"reported": names},
                        "No expectation given (use --expect gpu=H100,count=8)", criteria=["LIF-4"]))
        if expect.get("mem"):
            want_gb = float(expect["mem"])
            low = [m for m in mem if m / 1024 < want_gb * 0.9]
            C.append(mk("gpu.memory", "GPU memory matches expectation", FAIL if low else PASS, {"memory_mib": mem, "expected_gb": want_gb},
                        f"GPU memory {mem} MiB below {want_gb} GB" if low else "", "Check the SKU delivered for this node."))
        joined = " ".join(names).upper()
        if any(k in joined for k in CURRENT_GEN):
            st, why = PASS, "current-generation GPU"
        elif any(k in joined for k in PREV_GEN):
            st, why = WARN, "previous generation (Hopper / MI300); ClusterMAX expects Blackwell-class or MI355X for the top tiers"
        else:
            st, why = FAIL, "not a current training GPU"
        C.append(mk("gpu.generation", "Latest-generation GPUs on this node", st, names, why,
                    "Plan B200/B300/GB300 (or MI355X) capacity and publish the timeline.", ["AVA-1", "AVA-7"]))
        cur = any(k in joined for k in CURRENT_MODELS)
        C.append(mk("gpu.current_model", "GPU is a current model (H100/H200/A100/L40S/MI300X or newer)", PASS if cur else WARN, names,
                    "" if cur else "Model is not in the ClusterMAX current-model list", "Offer current models alongside this SKU.", ["AVA-2"]))

        # Driver / CUDA
        drv = g.get("driver") or ""
        need = driver_minimum(drv, mins)
        obs = {"driver": drv, "cuda": g.get("cuda"), "minimum_for_branch": need, "open_kernel_module": g.get("open_kernel_module")}
        if need is None:
            C.append(mk("gpu.driver_version", "NVIDIA driver at or above the published security minimum", WARN, obs,
                        f"Driver branch {drv.split('.')[0]} has no published patched release in the minimum-versions list (likely end of life)",
                        "Move to a supported driver branch at or above its security minimum.", ["SEC-17"]))
        elif P.version_ge(drv, need):
            C.append(mk("gpu.driver_version", "NVIDIA driver at or above the published security minimum", PASS, obs, criteria=["SEC-17"]))
        else:
            C.append(mk("gpu.driver_version", "NVIDIA driver at or above the published security minimum", FAIL, obs,
                        f"Driver {drv} is below {need} for its branch", f"Upgrade the NVIDIA driver to {need} or newer ({(mins.get('advisories') or {}).get('nvidiaDriver', '')}).", ["SEC-17"]))

        persist = [x["index"] for x in gpus if x.get("persistence") is False]
        C.append(mk("gpu.persistence", "Persistence mode enabled", WARN if persist else PASS, {"disabled_on": persist},
                    "Persistence mode off: slower job start and lost state between jobs" if persist else "",
                    "Enable nvidia-persistenced (systemctl enable --now nvidia-persistenced).", ["LIF-9"]))

        # Throttling
        hard = {x["index"]: [r for r in x["throttle_reasons"] if r in P.THROTTLE_FAIL] for x in gpus}
        hard = {k: v for k, v in hard.items() if v}
        soft = {x["index"]: [r for r in x["throttle_reasons"] if r in P.THROTTLE_WARN] for x in gpus}
        soft = {k: v for k, v in soft.items() if v}
        if all(x.get("throttle_mask") is None for x in gpus):
            C.append(mk("gpu.throttle", "No hardware clock throttling", UNKNOWN, None, "Driver did not report clock event reasons", criteria=["REL-16"]))
        elif hard:
            C.append(mk("gpu.throttle", "No hardware clock throttling", FAIL, hard,
                        "Hardware slowdown active: " + "; ".join(f"GPU{k}: {','.join(v)}" for k, v in hard.items()),
                        "Check cooling, fans, PSU and power capping on this node; drain until clocks recover.", ["REL-16", "REL-7"]))
        elif soft:
            C.append(mk("gpu.throttle", "No hardware clock throttling", WARN, soft, "Software thermal slowdown active",
                        "Check airflow and inlet temperature.", ["REL-16", "REL-7"]))
        else:
            C.append(mk("gpu.throttle", "No hardware clock throttling", PASS, None, criteria=["REL-16", "REL-7"]))

        temps = {x["index"]: x["temp_c"] for x in gpus if x.get("temp_c") is not None}
        hot = {k: v for k, v in temps.items() if v >= thr["temp_fail"]}
        warm = {k: v for k, v in temps.items() if thr["temp_warn"] <= v < thr["temp_fail"]}
        if not temps:
            C.append(mk("gpu.temperature", "GPU temperatures within limits", UNKNOWN, None, "No temperatures reported", criteria=["REL-7"]))
        else:
            st = FAIL if hot else WARN if warm else PASS
            C.append(mk("gpu.temperature", "GPU temperatures within limits", st, {"max_c": max(temps.values()), "per_gpu": temps},
                        (f"GPU temperature at or above {thr['temp_fail']:.0f} C on GPU " + ",".join(map(str, hot))) if hot else
                        (f"GPU temperature at or above {thr['temp_warn']:.0f} C" if warm else ""),
                        "Inspect cooling for this chassis.", ["REL-7", "REL-16"]))

        unc = {x["index"]: x["ecc_uncorrected"] for x in gpus if (x.get("ecc_uncorrected") or 0) > 0}
        if all(x.get("ecc_uncorrected") is None for x in gpus):
            C.append(mk("gpu.ecc", "No uncorrectable ECC errors", UNKNOWN, None, "ECC counters not reported (ECC disabled or unsupported)", criteria=["REL-15", "REL-8"]))
        else:
            C.append(mk("gpu.ecc", "No uncorrectable ECC errors", FAIL if unc else PASS, unc or None,
                        ("Uncorrectable (volatile) ECC errors on GPU " + ",".join(map(str, unc))) if unc else "",
                        "Drain the node, reset the GPU (nvidia-smi -r) and run dcgmi diag -r 3; RMA if it repeats.", ["REL-15", "REL-8"]))

        failed = [x["index"] for x in gpus if x.get("remap_failure")]
        pending = [x["index"] for x in gpus if x.get("remap_pending") or x.get("retired_pending")]
        if all(x.get("remap_failure") is None and x.get("remap_pending") is None and x.get("retired_pending") is None for x in gpus):
            C.append(mk("gpu.row_remap", "No pending page retirement / row remapping", UNKNOWN, None, "Not reported by this driver/GPU", criteria=["REL-8"]))
        else:
            st = FAIL if failed else WARN if pending else PASS
            C.append(mk("gpu.row_remap", "No pending page retirement / row remapping", st, {"remap_failure": failed, "pending": pending},
                        ("Row remapping failed on GPU " + ",".join(map(str, failed))) if failed else ("Reset pending on GPU " + ",".join(map(str, pending)) if pending else ""),
                        "Failed remap: RMA the GPU. Pending: drain and reset the GPU.", ["REL-8", "REL-15"]))

        degraded = {x["index"]: f"x{int(x['pcie_width'])}/x{int(x['pcie_width_max'])}" for x in gpus
                    if x.get("pcie_width") and x.get("pcie_width_max") and x["pcie_width"] < x["pcie_width_max"]}
        C.append(mk("gpu.pcie_link", "GPU PCIe link at full width", FAIL if degraded else PASS,
                    {"degraded": degraded, "gen": sorted({x.get("pcie_gen") for x in gpus if x.get("pcie_gen")})},
                    ("PCIe link width degraded on GPU " + ", ".join(f"{k} ({v})" for k, v in degraded.items())) if degraded else "Link generation may drop at idle; that is normal",
                    "Reseat the GPU/riser; check PCIe AER errors in dmesg.", ["REL-19", "REL-5"]))

        nv = f.get("nvlink") or {}
        if "reason" in nv:
            C.append(mk("gpu.nvlink", "All NVLink links up", UNKNOWN, None, nv["reason"], criteria=["REL-13"]))
        elif nv.get("links_total", 0) == 0:
            C.append(mk("gpu.nvlink", "All NVLink links up", NA, None, "No NVLink on this GPU model (PCIe card)", criteria=["REL-13"]))
        else:
            st = FAIL if nv["links_inactive"] else PASS
            C.append(mk("gpu.nvlink", "All NVLink links up", st, {"total": nv["links_total"], "inactive": nv["links_inactive"]},
                        f"{nv['links_inactive']} of {nv['links_total']} NVLink links inactive" if st == FAIL else "",
                        "Check fabric manager and NVSwitch health; drain the node.", ["REL-13"]))
            fm = f.get("fabricmanager")
            sxm8 = len(gpus) >= 8 and nv["links_total"] >= 8 * 12
            if sxm8:
                if fm is None:
                    C.append(mk("gpu.fabricmanager", "NVIDIA Fabric Manager running (NVSwitch systems)", UNKNOWN, None, "systemctl not available", criteria=["LIF-9"]))
                else:
                    C.append(mk("gpu.fabricmanager", "NVIDIA Fabric Manager running (NVSwitch systems)", PASS if fm == "active" else FAIL, fm,
                                "" if fm == "active" else f"nvidia-fabricmanager is {fm}",
                                "systemctl enable --now nvidia-fabricmanager (version must match the driver).", ["LIF-9"]))

        # XID
        x = f.get("xid") or {}
        if "reason" in x:
            C.append(mk("gpu.xid", "No critical XID events this boot", UNKNOWN, None, x["reason"], criteria=["REL-9", "REL-4"]))
        else:
            crit = [e for e in x["events"] if e["severity"] == "fail"]
            warn = [e for e in x["events"] if e["severity"] == "warn"]
            codes = sorted({e["xid"] for e in x["events"]})
            st = FAIL if crit else WARN if warn else PASS
            desc = "; ".join(f"XID {e['xid']} on {e['bus']} ({P.XID_CRITICAL.get(e['xid']) or P.XID_WARN.get(e['xid'], '')})" for e in (crit or warn)[:4])
            C.append(mk("gpu.xid", "No critical XID events this boot", st, {"source": x["source"], "xid_codes": codes, "count": len(x["events"])},
                        desc or (f"Only application-class XIDs {codes}" if codes else "No XID events"),
                        "Drain the node; XID 79/48/95/64 need a GPU reset or RMA.", ["REL-9", "REL-4"]))
            sx = x.get("sxid") or []
            C.append(mk("gpu.sxid", "No NVSwitch SXID events this boot", WARN if sx else PASS, [s["sxid"] for s in sx] or None,
                        f"{len(sx)} SXID events" if sx else "", "Check NVSwitch health and fabric manager logs.", ["REL-9"]))

        # GPUDirect RDMA
        mods = f.get("modules")
        ib_ports = (f.get("ib") or {}).get("ports") or []
        if mods is None:
            C.append(mk("gpu.gpudirect_rdma", "GPUDirect RDMA path available (dma_buf or nvidia_peermem)", UNKNOWN, None, "/proc/modules not readable", criteria=["LIF-8"]))
        elif not ib_ports:
            C.append(mk("gpu.gpudirect_rdma", "GPUDirect RDMA path available (dma_buf or nvidia_peermem)", NA if not (f.get("ib") or {}).get("devices") else UNKNOWN, None,
                        "No RDMA NICs on this node", criteria=["LIF-8"]))
        else:
            peermem = "nvidia_peermem" in mods
            dmabuf = bool(g.get("open_kernel_module")) and P.version_ge((f.get("kernel") or "0").split("-")[0], "5.12")
            obs = {"nvidia_peermem": peermem, "open_kernel_module": g.get("open_kernel_module"), "kernel": f.get("kernel")}
            if dmabuf:
                C.append(mk("gpu.gpudirect_rdma", "GPUDirect RDMA path available (dma_buf or nvidia_peermem)", PASS, obs, "dma_buf capable (open kernel module, kernel >= 5.12)", criteria=["LIF-8"]))
            elif peermem:
                C.append(mk("gpu.gpudirect_rdma", "GPUDirect RDMA path available (dma_buf or nvidia_peermem)", WARN, obs,
                            "Only the legacy nvidia_peermem path; ClusterMAX expects dma_buf with the open kernel module",
                            "Switch to the NVIDIA open kernel module (dma_buf GPUDirect RDMA).", ["LIF-8"]))
            else:
                C.append(mk("gpu.gpudirect_rdma", "GPUDirect RDMA path available (dma_buf or nvidia_peermem)", FAIL, obs,
                            "Neither dma_buf (open module) nor nvidia_peermem: NCCL will stage through host memory",
                            "Install the open kernel module (or load nvidia_peermem) so NCCL can use GPUDirect RDMA.", ["LIF-8"]))
            gdr = "gdrdrv" in mods or bool((f.get("software") or {}).get("gdrapi_lib"))
            C.append(mk("gpu.gdrcopy", "GDRCopy installed", PASS if gdr else WARN, gdr, "" if gdr else "gdrdrv module and libgdrapi not found",
                        "Install GDRCopy (gdrdrv) for low-latency GPU memory copies.", ["LIF-8"]))

        params = g.get("params")
        if params is None:
            C.append(mk("profiling.ncu", "ncu hardware counters available to non-root users", UNKNOWN, None, "/proc/driver/nvidia/params not readable", criteria=["MON-1"]))
        else:
            v = params.get("RmProfilingAdminOnly")
            ok = v == "0"
            C.append(mk("profiling.ncu", "ncu hardware counters available to non-root users", PASS if ok else FAIL, {"RmProfilingAdminOnly": v},
                        "" if ok else "Profiling restricted to admins",
                        "Set options nvidia NVreg_RestrictProfilingToAdminUsers=0 in /etc/modprobe.d and reload the driver.", ["MON-1"]))

    pep = f.get("perf_event_paranoid")
    if pep is not None:
        try:
            ok = int(pep) <= 1 and (f.get("kptr_restrict") in (None, "0"))
        except ValueError:
            ok = False
        C.append(mk("profiling.perf", "perf usable by non-root users", PASS if ok else WARN, {"perf_event_paranoid": pep, "kptr_restrict": f.get("kptr_restrict")},
                    "" if ok else "perf restricted (ClusterMAX expects perf_event_paranoid <= 1, kptr_restrict = 0)",
                    "sysctl kernel.perf_event_paranoid=1 kernel.kptr_restrict=0 (persist in /etc/sysctl.d).", ["MON-12"]))

    # --- PCIe ACS --------------------------------------------------------------
    acs = f.get("acs") or {}
    if "reason" in acs:
        C.append(mk("pcie.acs", "PCIe ACS disabled on GPU/NIC switches (bare metal)", UNKNOWN, None, acs["reason"], criteria=["LIF-8"]))
    elif acs.get("acs_capable_ports", 0) == 0:
        C.append(mk("pcie.acs", "PCIe ACS disabled on GPU/NIC switches (bare metal)", NA, None, "No ACS-capable ports reported", criteria=["LIF-8"]))
    else:
        en = acs.get("acs_enabled") or []
        C.append(mk("pcie.acs", "PCIe ACS disabled on GPU/NIC switches (bare metal)", WARN if en else PASS, {"enabled_on": en[:12], "ports": acs["acs_capable_ports"]},
                    f"ACS redirect enabled on {len(en)} ports: GPU-NIC peer traffic goes through the root complex" if en else "",
                    "On bare metal, disable ACS on PCIe switches below the GPUs/NICs (setpci at boot). Keep it on for VM passthrough.", ["LIF-8"]))

    # --- InfiniBand / RoCE -----------------------------------------------------
    ib = f.get("ib") or {}
    ports = ib.get("ports")
    exp_ib = int(expect["ib"]) if expect.get("ib") else None
    if ports is None:
        why = ib.get("reason", "")
        if ib.get("devices"):
            why += f" (RDMA devices present: {', '.join(ib['devices'][:8])}; install infiniband-diags)"
        st = FAIL if exp_ib else UNKNOWN
        C.append(mk("ib.present", "InfiniBand / RoCE fabric present", st, None, why, "Install infiniband-diags (ibstat) or fix the RDMA stack.", ["NET-2"]))
        C.append(mk("ib.ports_up", "All RDMA ports active", st, None, why, "Install infiniband-diags (ibstat).", ["REL-21", "REL-10"]))
    elif not ports:
        C.append(mk("ib.present", "InfiniBand / RoCE fabric present", FAIL, 0, "ibstat shows no RDMA devices",
                    "A scale-out fabric (400G+ IB or RoCEv2) is required for multi-node training.", ["NET-2"]))
    else:
        ibl = [p for p in ports if p["link_layer"].lower() == "infiniband"]
        roce = [p for p in ports if p["link_layer"].lower() == "ethernet"]
        # The compute fabric is InfiniBand when present; Ethernet RDMA ports are
        # then front-end/storage. Without IB, fast Ethernet RDMA ports are RoCE.
        compute = [p for p in (ibl or roce) if (p.get("rate") or 0) >= 100]
        rates = sorted({p["rate"] for p in compute if p.get("rate")})
        st = PASS if compute else WARN
        C.append(mk("ib.present", "InfiniBand / RoCE fabric present", st,
                    {"infiniband_ports": len(ibl), "ethernet_rdma_ports": len(roce), "rates_gbps": rates},
                    "" if compute else "No RDMA port at 100 Gb/s or faster", "Provide a 400G+ scale-out fabric.", ["NET-2"]))
        down = [p for p in ports if p["link_layer"].lower() == "infiniband" and p["state"].lower() != "active"]
        down_eth = [p for p in roce if p["state"].lower() != "active" and (p.get("rate") or 0) >= 100]
        active_n = len([p for p in compute if p["state"].lower() == "active"])
        obs = {"active_fast_ports": active_n, "down": [f"{p['ca']}/{p['port']} {p['state']}/{p['phys']}" for p in down + down_eth]}
        if down or (exp_ib and active_n < exp_ib):
            C.append(mk("ib.ports_up", "All RDMA ports active", FAIL, obs,
                        (f"{len(down)} InfiniBand port(s) not Active: " + ", ".join(obs["down"])) if down else f"{active_n} active fast ports, {exp_ib} expected",
                        "Check cable/transceiver and switch port; drain the node until the rail is back.", ["REL-21", "REL-10", "REL-6"]))
        elif down_eth:
            C.append(mk("ib.ports_up", "All RDMA ports active", WARN, obs, "Ethernet RDMA port(s) down", "Check the RoCE links.", ["REL-21", "REL-10"]))
        else:
            C.append(mk("ib.ports_up", "All RDMA ports active", PASS, obs, criteria=["REL-21", "REL-10"]))
        names_ok = all(p["ca"].startswith("mlx5_") for p in compute) if compute else None
        if names_ok is not None:
            C.append(mk("ib.hca_naming", "HCAs named mlx5_* (NCCL_IB_HCA friendly)", PASS if names_ok else WARN, sorted({p["ca"] for p in compute}),
                        "" if names_ok else "Non-standard HCA names break common NCCL_IB_HCA settings", "Keep the default mlx5_* naming.", ["LIF-9"]))
        fws = sorted({p["fw"] for p in compute if p.get("fw")})
        trains = mins.get("connectxFirmwareTrains") or {}
        low = []
        for fw in fws:
            parts = fw.split(".")
            if len(parts) >= 3 and parts[0] in trains:
                need = int(trains[parts[0]])
                have = int(parts[1]) * 100 + int(parts[2][:2] or 0)
                if have < need:
                    low.append(fw)
        if fws:
            C.append(mk("ib.firmware", "ConnectX firmware at or above the published minimum", WARN if low else PASS, {"firmware": fws},
                        f"Firmware {', '.join(low)} looks older than the published minimum for its train (approximate; confirm with cmax audit)" if low else "",
                        "Update ConnectX firmware (mlxfwmanager).", ["SEC-17"]))
        pk = ib.get("pkeys")
        if ibl:
            if pk is None:
                C.append(mk("ib.pkey", "Tenant PKey configured on InfiniBand ports", UNKNOWN, None, "PKey table not readable", criteria=["SEC-9"]))
            else:
                vals = sorted({v for vs in pk.values() for v in vs})
                tenant = [v for v in vals if v not in ("0xffff", "0x7fff")]
                C.append(mk("ib.pkey", "Tenant PKey configured on InfiniBand ports", PASS if tenant else WARN, vals,
                            "" if tenant else "Only the default partition: tenants are not separated by PKey",
                            "Assign a per-tenant PKey (limited membership) via the subnet manager / UFM.", ["SEC-9"]))

    # --- NCCL config -------------------------------------------------------------
    conf = f.get("nccl_conf")
    lines = [ln.split("#")[0].strip() for ln in (conf or "").splitlines() if ln.split("#")[0].strip()]
    forced = [ln for ln in lines if ln.split("=")[0].strip() in ("NCCL_MIN_NCHANNELS", "NCCL_PROTO", "NCCL_ALGO")]
    C.append(mk("nccl.autoconfig", "NCCL tuning left to auto-config", WARN if forced else PASS, forced or ("no /etc/nccl.conf" if conf is None else "no forced settings"),
                ("Forced in /etc/nccl.conf: " + ", ".join(forced)) if forced else "",
                "Remove NCCL_MIN_NCHANNELS / NCCL_PROTO / NCCL_ALGO from /etc/nccl.conf.", ["NET-5"]))
    has_ib = any(p["link_layer"].lower() == "infiniband" for p in (ports or []))
    roce_ports = [] if has_ib else [p for p in (ports or []) if p["link_layer"].lower() == "ethernet" and (p.get("rate") or 0) >= 100]
    if roce_ports:
        gid = any(ln.replace(" ", "") == "NCCL_IB_GID_INDEX=3" for ln in lines)
        C.append(mk("nccl.roce_gid", "NCCL_IB_GID_INDEX=3 set for RoCEv2", PASS if gid else WARN, bool(gid), "" if gid else "RoCE fabric without NCCL_IB_GID_INDEX=3 in /etc/nccl.conf",
                    "Add NCCL_IB_GID_INDEX=3 to /etc/nccl.conf.", ["NET-4"]))
    elif ports:
        C.append(mk("nccl.roce_gid", "NCCL_IB_GID_INDEX=3 set for RoCEv2", NA, None, "InfiniBand fabric; not applicable", criteria=["NET-4"]))

    sw = f.get("software") or {}
    C.append(mk("sw.hpcx", "HPC-X / MPI available", PASS if sw.get("hpcx") else WARN, bool(sw.get("hpcx")),
                "" if sw.get("hpcx") else "/opt/hpcx not found", "Install NVIDIA HPC-X (or expose it as an Lmod module).", ["NET-3"]))
    C.append(mk("sw.nccl", "NCCL installed on the host", PASS if sw.get("nccl_lib") else WARN, sw.get("nccl_lib"),
                "" if sw.get("nccl_lib") else "libnccl not in the linker cache (fine if every job brings its own container)",
                "Install a current NCCL in the base image."))
    C.append(mk("sw.nvcc", "CUDA toolkit (nvcc) installed", PASS if sw.get("nvcc") else WARN, sw.get("nvcc"),
                "" if sw.get("nvcc") else "nvcc not found", "Install the CUDA toolkit or an Lmod module for it."))
    if sw.get("nvcc") and mins.get("cudaToolkit"):
        okc = P.version_ge(sw["nvcc"], mins["cudaToolkit"])
        C.append(mk("sw.cuda_security", "CUDA toolkit at or above the published security minimum", PASS if okc else WARN, sw["nvcc"],
                    "" if okc else f"CUDA {sw['nvcc']} below {mins['cudaToolkit']}", f"Update the CUDA toolkit to {mins['cudaToolkit']}+.", ["SEC-17"]))

    # --- Containers ----------------------------------------------------------------
    c = f.get("containers") or {}
    ctk = c.get("nvidia_ctk") or c.get("nvidia_container_cli")
    need = mins.get("nvidiaContainerToolkit")
    if ctk:
        okt = P.version_ge(ctk, need) if need else True
        C.append(mk("containers.toolkit", "NVIDIA Container Toolkit patched", PASS if okt else FAIL, {"version": ctk, "minimum": need},
                    "" if okt else f"Container Toolkit {ctk} below {need} (container escape CVEs, e.g. CVE-2024-0132, CVE-2025-23266)",
                    f"Upgrade nvidia-container-toolkit to {need}+ on every node.", ["SEC-15", "SEC-16", "SEC-14"]))
    else:
        C.append(mk("containers.toolkit", "NVIDIA Container Toolkit patched", UNKNOWN if not has_gpu else WARN, None,
                    "nvidia-ctk / nvidia-container-cli not found", "Install the NVIDIA Container Toolkit.", ["SEC-15", "SEC-16"]))
    if c.get("docker") and mins.get("docker"):
        okd = P.version_ge(c["docker"], mins["docker"])
        C.append(mk("containers.docker", "Docker Engine at or above the published minimum", PASS if okd else WARN, c["docker"],
                    "" if okd else f"Docker {c['docker']} below {mins['docker']}", "Update Docker Engine.", ["SEC-17"]))
    sl = f.get("slurm") or {}
    if sl.get("present"):
        en, px = c.get("enroot"), c.get("pyxis")
        st = PASS if (en and px) else WARN if (en or px) else FAIL
        C.append(mk("containers.pyxis", "Pyxis + Enroot for containers under Slurm", st, {"enroot": en, "pyxis": px},
                    "" if st == PASS else "Pyxis/Enroot missing", "Install Enroot and the Pyxis SPANK plugin.", ["SLU-7"]))
        app = c.get("apptainer") or c.get("singularity")
        C.append(mk("containers.apptainer", "Apptainer / Singularity available", PASS if app else WARN, app, "" if app else "Not installed",
                    "Install Apptainer for HPC users."))

    # --- Slurm -----------------------------------------------------------------------
    if sl.get("present"):
        cfg = sl.get("config")
        if cfg is None:
            for cid, t, crit in (("slurm.healthcheck", "Slurm HealthCheckProgram configured", ["MON-16", "MON-6"]),
                                 ("slurm.topology", "Slurm topology plugin configured", ["SLU-5", "NET-1"])):
                C.append(mk(cid, t, UNKNOWN, None, sl.get("reason", "scontrol show config failed"), criteria=crit))
        else:
            hcp = cfg.get("HealthCheckProgram", "(null)")
            hci = cfg.get("HealthCheckInterval", "0")
            has = hcp not in ("", "(null)")
            dcgm_based = has and any(k in hcp.lower() for k in ("predge", "nhc", "dcgm"))
            st = PASS if has and dcgm_based else WARN if has else FAIL
            C.append(mk("slurm.healthcheck", "Slurm HealthCheckProgram configured", st, {"HealthCheckProgram": hcp, "HealthCheckInterval": hci},
                        "" if st == PASS else ("HealthCheckProgram set but not recognised as GPU-aware" if has else "No HealthCheckProgram: failing nodes keep taking jobs"),
                        "Set HealthCheckProgram to a GPU-aware check (e.g. predge-ready health --drain) with HealthCheckInterval=60.", ["MON-16", "MON-6", "MON-3"]))
            tp = cfg.get("TopologyPlugin", "")
            topo = tp not in ("", "(null)", "topology/default", "topology/flat")
            C.append(mk("slurm.topology", "Slurm topology plugin configured", PASS if topo else WARN, tp,
                        "" if topo else "No topology plugin: jobs ignore switch locality",
                        "Configure topology.yaml (block or tree) from the fabric layout.", ["SLU-5", "NET-1"]))
            acct = cfg.get("AccountingStorageType", "")
            C.append(mk("slurm.accounting", "sacct job accounting enabled", PASS if "slurmdbd" in acct else WARN, acct,
                        "" if "slurmdbd" in acct else "No slurmdbd accounting", "Enable slurmdbd accounting.", ["MON-15"]))
            gres = cfg.get("GresTypes", "")
            ng = sl.get("node_gres") or ""
            okg = "gpu" in gres and ("gpu" in ng or not ng)
            C.append(mk("slurm.gres", "GPUs scheduled as GRES (per-GPU allocation, CUDA_VISIBLE_DEVICES set)", PASS if okg else WARN, {"GresTypes": gres, "node_gres": ng},
                        "" if okg else "GPU GRES not configured: sub-node jobs cannot get isolated GPUs",
                        "Configure gres.conf with AutoDetect=nvml and GresTypes=gpu.", ["ORC-6"]))
            mpi = cfg.get("MpiDefault", "")
            C.append(mk("slurm.pmix", "srun integrated with PMIx", PASS if "pmix" in mpi else WARN, mpi, "" if "pmix" in mpi else "MpiDefault is not pmix",
                        "Build Slurm with PMIx and set MpiDefault=pmix.", ["NET-3"]))
        C.append(mk("slurm.lmod", "Lmod modules available", PASS if sw.get("lmod") else WARN, bool(sw.get("lmod")), "" if sw.get("lmod") else "Lmod not found",
                    "Install Lmod with modules for CUDA, HPC-X and NCCL.", ["SLU-6"]))

    # --- Kubernetes --------------------------------------------------------------------
    k = f.get("k8s") or {}
    if k.get("kubectl") and k.get("api_ok"):
        scs = k.get("storageclasses") or []
        rwx_words = ("nfs", "cephfs", "weka", "lustre", "gpfs", "spectrum", "vast", "efs", "filestore", "beegfs", "juicefs", "ddn", "exa")
        rwx = [s["name"] for s in scs if any(w in s["provisioner"].lower() for w in rwx_words)]
        default = [s["name"] for s in scs if s["default"]]
        C.append(mk("k8s.rwx", "ReadWriteMany StorageClass available", PASS if rwx else WARN, {"storageclasses": [s["name"] for s in scs], "rwx_capable": rwx},
                    "" if rwx else "No RWX-capable provisioner recognised", "Add an RWX CSI driver backed by the shared filesystem.", ["STO-3"]))
        C.append(mk("k8s.default_sc", "Default StorageClass set", PASS if default else WARN, default, "" if default else "No default StorageClass",
                    "Mark one StorageClass as default.", ["K8S-5"]))
        C.append(mk("k8s.kubectl", "kubectl access works", PASS, k.get("nodes"), criteria=["K8S-3"]))
        ops = k.get("operators") or {}
        for name, crit in (("gpu-operator", []), ("network-operator", []), ("dcgm-exporter", ["MON-2"]), ("node-problem-detector", ["REL-12"])):
            if name in ops:
                C.append(mk(f"k8s.{name}", f"Kubernetes {name} deployed", PASS if ops[name] else WARN, ops[name], "" if ops[name] else f"{name} not found",
                            f"Deploy {name}.", crit))
    elif k.get("kubelet") or k.get("kubectl"):
        C.append(mk("k8s.kubectl", "kubectl access works", UNKNOWN, None, k.get("reason") or "kubectl not usable from this node", criteria=["K8S-3"]))

    # --- Shared storage -------------------------------------------------------------------
    mt = f.get("mounts") or {}
    if "reason" in mt:
        C.append(mk("storage.shared_fs", "Shared filesystem mounted", UNKNOWN, None, mt["reason"], criteria=["STO-1", "STO-4"]))
    else:
        sh = mt.get("shared") or []
        par = [m for m in sh if m["fstype"] in PARALLEL_FS]
        obs = [f"{m['mountpoint']} ({m['fstype']})" for m in sh][:8]
        if par:
            st, why = PASS, "Parallel filesystem mounted"
        elif sh:
            st, why = WARN, "Network filesystem (NFS-class) mounted; no parallel filesystem"
        else:
            st, why = FAIL, "No shared filesystem mounted on this node"
        C.append(mk("storage.parallel_fs", "High-performance parallel filesystem mounted", st, obs, why,
                    "Provide a parallel filesystem (Weka, VAST, DDN/Lustre, GPFS) mounted on all nodes.", ["STO-1"]))
        if sh:
            resp = mt.get("responsive")
            C.append(mk("storage.shared_fs", "Shared filesystem mounted and responsive", PASS if resp else FAIL, mt.get("probe"),
                        "" if resp else f"{mt.get('probe')} did not respond to statfs within 8 s",
                        "Check the storage client and network; a hung mount stalls every job.", ["STO-4"]))

    # --- Monitoring / remediation ----------------------------------------------------------
    agents = f.get("agents")
    units = f.get("units") or []
    if agents is None:
        C.append(mk("monitoring.exporters", "GPU and node metrics exporters running", UNKNOWN, None, "ps not available", criteria=["MON-10", "REL-17"]))
    else:
        dcgm_exp = "dcgm-exporter" in agents or (k.get("operators") or {}).get("dcgm-exporter")
        node_exp = "node-exporter" in agents
        st = PASS if (dcgm_exp and node_exp) else WARN if (dcgm_exp or node_exp) else FAIL
        C.append(mk("monitoring.exporters", "GPU and node metrics exporters running", st, {"dcgm-exporter": bool(dcgm_exp), "node-exporter": node_exp},
                    "" if st == PASS else "Missing " + ", ".join(n for n, v in (("dcgm-exporter", dcgm_exp), ("node-exporter", node_exp)) if not v),
                    "Run dcgm-exporter and node-exporter on every GPU node and scrape them into Prometheus/Grafana.", ["MON-10", "MON-14", "REL-17", "MON-2"]))
        C.append(mk("monitoring.ipmi", "IPMI / BMC exporter (fans, PSU, inlet temperature)", PASS if "ipmi-exporter" in agents else WARN, "ipmi-exporter" in agents,
                    "" if "ipmi-exporter" in agents else "No ipmi_exporter process", "Run ipmi_exporter (or Redfish exporter) for fan speed and PSU telemetry.", ["REL-20"]))
        dcgm_host = "nv-hostengine" in agents or any("dcgm" in u for u in units)
        if has_gpu:
            C.append(mk("monitoring.dcgm", "DCGM host engine running (passive GPU health)", PASS if dcgm_host else WARN,
                        {"nv-hostengine": "nv-hostengine" in agents, "dcgm_version": sw.get("dcgm")},
                        "" if dcgm_host else "nv-hostengine not running: no DCGM background health watches",
                        "Install DCGM and enable nvidia-dcgm.service; set health watches (dcgmi health -s a).", ["REL-18", "MON-6"]))
        remed = [a for a in agents if a in ("gpud", "node-problem-detector", "nvsentinel")]
        remed += [u for u in units if u.startswith("predge-ready-health") or u.startswith("nhc")]
        hc = ((sl.get("config") or {}).get("HealthCheckProgram") or "(null)") if sl.get("present") else "(null)"
        if hc not in ("", "(null)"):
            remed.append(f"HealthCheckProgram={hc}")
        C.append(mk("health.auto_drain", "Failing nodes are drained automatically", PASS if remed else FAIL, remed or None,
                    "" if remed else "No automatic health check / drain found (HealthCheckProgram, NHC, gpud, NPD, NVSentinel, predge-ready timer)",
                    "Install predge-ready health --drain as Slurm HealthCheckProgram or a systemd timer (see docs/health-checks.md).", ["MON-8", "REL-25", "MON-3"]))

    # --- Active tests -----------------------------------------------------------------------
    act = f.get("active")
    if act is not None:
        C.extend(active_checks(act, gpus))
    for chk in C:
        chk["node"] = f.get("host")
    return C


def active_checks(act: Dict[str, Any], gpus: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    C = []
    d = act.get("dcgm_diag") or {}
    if "reason" in d:
        C.append(mk("active.dcgm_diag", "DCGM diagnostic (dcgmi diag)", UNKNOWN, None, d["reason"], criteria=["MON-7"]))
    else:
        st = FAIL if d.get("failed") else WARN if d.get("warnings") else PASS if d.get("passed") else UNKNOWN
        C.append(mk("active.dcgm_diag", f"DCGM diagnostic (dcgmi diag -r {d.get('level')})", st, {"passed": d.get("passed"), "failed": d.get("failed"), "warnings": d.get("warnings")},
                    "; ".join(d.get("failed") or d.get("warnings") or []) or ("" if st != UNKNOWN else "No test results parsed"),
                    "Drain the node and investigate the failing DCGM test.", ["MON-7", "MON-3"]))
    n = act.get("nccl_allreduce") or {}
    if "reason" in n:
        C.append(mk("active.nccl", "Single-node NCCL all_reduce bandwidth", UNKNOWN, None, n["reason"], criteria=["NET-10", "REL-11"]))
    else:
        bw, floor = n.get("busbw_gbs"), n.get("floor_gbs")
        st = UNKNOWN if bw is None else (FAIL if floor and bw < floor else PASS)
        C.append(mk("active.nccl", "Single-node NCCL all_reduce bandwidth", st, {"busbw_gbs": bw, "floor_gbs": floor, "gpus": n.get("gpus")},
                    (f"Bus bandwidth {bw} GB/s below {floor} GB/s floor" if st == FAIL else "") if bw is not None else "Could not parse all_reduce_perf output",
                    "Check NVLink/NVSwitch, fabric manager and GPU clocks.", ["NET-10", "REL-11"]))
    b = act.get("ib_write_bw") or {}
    if "reason" in b:
        C.append(mk("active.ib_write_bw", "RDMA loopback bandwidth (ib_write_bw)", UNKNOWN, None, b["reason"], criteria=["NET-10", "REL-1"]))
    else:
        bw, rate = b.get("gbps"), b.get("port_rate_gbps")
        st = UNKNOWN if bw is None else (FAIL if rate and bw < 0.8 * rate else PASS)
        C.append(mk("active.ib_write_bw", "RDMA loopback bandwidth (ib_write_bw)", st, b,
                    (f"{bw} Gb/s on a {rate} Gb/s port" if st == FAIL else "") if bw is not None else "Could not parse ib_write_bw output",
                    "Check cables, transceivers and switch counters for this rail.", ["NET-10", "REL-1"]))
    gm = act.get("gemm") or {}
    if "results" not in gm:
        C.append(mk("active.gemm", "GEMM throughput (bf16, torch)", UNKNOWN, None, gm.get("reason") or gm.get("error", "no result"), criteria=["MON-5"]))
    else:
        floor = gm.get("floor_bf16")
        name = gm["results"][0]["name"] if gm["results"] else ""
        if floor and "pcie" in name.lower():
            floor = round(floor * 0.75)
        slow = [r["gpu"] for r in gm["results"] if floor and r.get("bf16", 0) < floor]
        C.append(mk("active.gemm", "GEMM throughput (bf16, torch)", FAIL if slow else PASS,
                    {"bf16_tflops": [r.get("bf16") for r in gm["results"]], "floor_bf16": floor},
                    ("Slow GPUs: " + ",".join(map(str, slow))) if slow else "",
                    "Check clocks, power limits and throttling on the slow GPUs.", ["MON-5"]))
    return C


def cluster_checks(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Checks across nodes: version consistency and PKey consistency."""
    C: List[Dict[str, Any]] = []
    if len(nodes) < 2:
        return C
    drivers = {n["facts"]["host"]: (n["facts"].get("gpu") or {}).get("driver") for n in nodes}
    vals = {v for v in drivers.values() if v}
    if vals:
        st = PASS if len(vals) == 1 else WARN
        C.append(mk("cluster.driver_consistency", "Same NVIDIA driver on every node", st, drivers,
                    "" if st == PASS else f"{len(vals)} different driver versions", "Roll one image to every node.", ["REL-14"]))
    models = {n["facts"]["host"]: sorted({g["name"] for g in (n["facts"].get("gpu") or {}).get("gpus") or []}) for n in nodes}
    distinct = {tuple(v) for v in models.values() if v}
    if distinct:
        C.append(mk("cluster.gpu_consistency", "Same GPU model on every node", PASS if len(distinct) == 1 else WARN, models,
                    "" if len(distinct) == 1 else "Mixed GPU models in one cluster", "Keep partitions homogeneous.", ["REL-14"]))
    pk = {n["facts"]["host"]: sorted({v for vs in ((n["facts"].get("ib") or {}).get("pkeys") or {}).values() for v in vs}) for n in nodes}
    pvals = {tuple(v) for v in pk.values() if v}
    if pvals:
        C.append(mk("cluster.pkey_consistency", "Same PKeys on every node", PASS if len(pvals) == 1 else FAIL, pk,
                    "" if len(pvals) == 1 else "PKey tables differ between nodes", "Fix partition membership in the subnet manager.", ["REL-23"]))
    for c in C:
        c["node"] = "cluster"
    return C
