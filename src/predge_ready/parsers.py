"""Pure parsers for tool output. No I/O here, so every parser is unit-testable."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

GPU_BASE_FIELDS = [
    "index",
    "name",
    "uuid",
    "pci.bus_id",
    "memory.total",
    "driver_version",
    "temperature.gpu",
    "clocks.sm",
    "clocks.max.sm",
    "power.draw",
    "power.limit",
    "persistence_mode",
    "pcie.link.gen.current",
    "pcie.link.gen.max",
    "pcie.link.width.current",
    "pcie.link.width.max",
    "ecc.errors.uncorrected.volatile.total",
    "ecc.errors.corrected.volatile.total",
]
# Queried separately because older drivers reject some of them.
GPU_EXTRA_FIELDS = [
    "clocks_event_reasons.active",
    "retired_pages.pending",
    "remapped_rows.pending",
    "remapped_rows.failure",
]
GPU_LEGACY_THROTTLE_FIELD = "clocks_throttle_reasons.active"

# nvidia-smi clocks event (throttle) reason bits.
THROTTLE_BITS = {
    0x1: "GpuIdle",
    0x2: "ApplicationsClocksSetting",
    0x4: "SwPowerCap",
    0x8: "HwSlowdown",
    0x10: "SyncBoost",
    0x20: "SwThermalSlowdown",
    0x40: "HwThermalSlowdown",
    0x80: "HwPowerBrakeSlowdown",
    0x100: "DisplayClockSetting",
}
THROTTLE_FAIL = {"HwSlowdown", "HwThermalSlowdown", "HwPowerBrakeSlowdown"}
THROTTLE_WARN = {"SwThermalSlowdown"}


def _num(value: str) -> Optional[float]:
    value = value.strip()
    if not value or value.startswith("[") or value.upper() in ("N/A", "NONE"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _flag(value: str) -> Optional[bool]:
    v = value.strip().lower()
    if v in ("yes", "enabled", "1", "true"):
        return True
    if v in ("no", "disabled", "0", "false"):
        return False
    return None


def parse_gpu_csv(text: str, fields: List[str]) -> List[Dict[str, Any]]:
    """Parse ``nvidia-smi --query-gpu=... --format=csv,noheader,nounits``."""
    gpus = []
    for line in text.strip().splitlines():
        if not line.strip():
            continue
        cols = [c.strip() for c in line.split(",")]
        if len(cols) < len(fields):
            continue
        gpus.append(dict(zip(fields, cols)))
    return gpus


def normalize_gpu(raw: Dict[str, str]) -> Dict[str, Any]:
    g: Dict[str, Any] = {
        "index": int(_num(raw.get("index", "")) or 0),
        "name": raw.get("name", ""),
        "uuid": raw.get("uuid", ""),
        "bus_id": raw.get("pci.bus_id", ""),
        "memory_mib": _num(raw.get("memory.total", "")),
        "driver": raw.get("driver_version", ""),
        "temp_c": _num(raw.get("temperature.gpu", "")),
        "sm_clock": _num(raw.get("clocks.sm", "")),
        "sm_clock_max": _num(raw.get("clocks.max.sm", "")),
        "power_w": _num(raw.get("power.draw", "")),
        "power_limit_w": _num(raw.get("power.limit", "")),
        "persistence": _flag(raw.get("persistence_mode", "")),
        "pcie_gen": _num(raw.get("pcie.link.gen.current", "")),
        "pcie_gen_max": _num(raw.get("pcie.link.gen.max", "")),
        "pcie_width": _num(raw.get("pcie.link.width.current", "")),
        "pcie_width_max": _num(raw.get("pcie.link.width.max", "")),
        "ecc_uncorrected": _num(raw.get("ecc.errors.uncorrected.volatile.total", "")),
        "ecc_corrected": _num(raw.get("ecc.errors.corrected.volatile.total", "")),
        "retired_pending": _flag(raw.get("retired_pages.pending", "")),
        "remap_pending": _flag(raw.get("remapped_rows.pending", "")),
        "remap_failure": _flag(raw.get("remapped_rows.failure", "")),
    }
    mask = raw.get("clocks_event_reasons.active") or raw.get(GPU_LEGACY_THROTTLE_FIELD) or ""
    g["throttle_mask"] = None
    g["throttle_reasons"] = []
    mask = mask.strip()
    if mask.lower().startswith("0x"):
        try:
            m = int(mask, 16)
            g["throttle_mask"] = m
            g["throttle_reasons"] = [name for bit, name in THROTTLE_BITS.items() if m & bit]
        except ValueError:
            pass
    return g


def parse_cuda_version(nvidia_smi_text: str) -> Optional[str]:
    m = re.search(r"CUDA Version:\s*([0-9.]+)", nvidia_smi_text)
    return m.group(1) if m else None


def count_lspci_gpus(text: str) -> int:
    """Count NVIDIA GPU functions in ``lspci -d 10de: -nn`` output (NVSwitches are bridges)."""
    n = 0
    for line in text.splitlines():
        if "NVIDIA" not in line and "10de:" not in line:
            continue
        if re.search(r"3D controller|VGA compatible controller|\[030[02]\]", line):
            n += 1
    return n


XID_RE = re.compile(r"NVRM: Xid \(PCI:([0-9a-fA-F:.]+)\): (\d+), ?(.*)")
SXID_RE = re.compile(r"SXid \(PCI:([0-9a-fA-F:.]+)\): (\d+), ?(.*)")

# XID handling, following NVIDIA's XID catalogue guidance.
XID_CRITICAL = {
    48: "Double-bit ECC error",
    61: "Internal micro-controller breakpoint/warning",
    62: "Internal micro-controller halt",
    64: "ECC page retirement or row remapping failure",
    74: "NVLink error",
    79: "GPU has fallen off the bus",
    92: "High single-bit ECC error rate",
    95: "Uncontained ECC error",
    119: "GSP RPC timeout",
    120: "GSP error",
    140: "Unrecovered ECC error",
}
XID_WARN = {
    63: "ECC page retirement or row remapping recorded (reset to apply)",
    94: "Contained ECC error (reset to apply)",
}
# 13, 31, 43, 45 and similar are usually caused by the application and are
# reported as info only.


def parse_xids(text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    xids, sxids = [], []
    for line in text.splitlines():
        m = XID_RE.search(line)
        if m:
            code = int(m.group(2))
            sev = "fail" if code in XID_CRITICAL else ("warn" if code in XID_WARN else "info")
            xids.append({"bus": m.group(1), "xid": code, "severity": sev, "message": m.group(3).strip()[:160]})
            continue
        m = SXID_RE.search(line)
        if m:
            sxids.append({"bus": m.group(1), "sxid": int(m.group(2)), "message": m.group(3).strip()[:160]})
    return xids, sxids


def parse_nvlink_status(text: str) -> Dict[str, Any]:
    """Parse ``nvidia-smi nvlink -s``."""
    per_gpu: Dict[str, Dict[str, int]] = {}
    current = None
    for line in text.splitlines():
        m = re.match(r"GPU (\d+):", line.strip())
        if m:
            current = m.group(1)
            per_gpu[current] = {"active": 0, "inactive": 0}
            continue
        m = re.match(r"\s*Link (\d+):\s*(.*)", line)
        if m and current is not None:
            if "inactive" in m.group(2).lower():
                per_gpu[current]["inactive"] += 1
            else:
                per_gpu[current]["active"] += 1
    total = sum(v["active"] + v["inactive"] for v in per_gpu.values())
    inactive = sum(v["inactive"] for v in per_gpu.values())
    return {"per_gpu": per_gpu, "links_total": total, "links_inactive": inactive}


def parse_ibstat(text: str) -> List[Dict[str, Any]]:
    ports: List[Dict[str, Any]] = []
    ca = fw = None
    port: Optional[Dict[str, Any]] = None
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"CA '([^']+)'", line)
        if m:
            ca, fw, port = m.group(1), None, None
            continue
        m = re.match(r"Firmware version:\s*(\S+)", line)
        if m:
            fw = m.group(1)
            continue
        m = re.match(r"Port (\d+):", line)
        if m and ca:
            port = {"ca": ca, "port": int(m.group(1)), "fw": fw, "state": "", "phys": "", "rate": None, "link_layer": ""}
            ports.append(port)
            continue
        if port is None:
            continue
        if line.startswith("State:"):
            port["state"] = line.split(":", 1)[1].strip()
        elif line.startswith("Physical state:"):
            port["phys"] = line.split(":", 1)[1].strip()
        elif line.startswith("Rate:"):
            port["rate"] = _num(line.split(":", 1)[1])
        elif line.startswith("Link layer:"):
            port["link_layer"] = line.split(":", 1)[1].strip()
    return ports


def parse_kv_config(text: str) -> Dict[str, str]:
    """Parse ``scontrol show config`` (``Key = value`` lines)."""
    cfg = {}
    for line in text.splitlines():
        if " = " in line:
            k, v = line.split(" = ", 1)
            cfg[k.strip()] = v.strip()
    return cfg


def parse_mounts(text: str) -> List[Dict[str, str]]:
    mounts = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            mounts.append({"source": parts[0], "mountpoint": parts[1].replace("\\040", " "), "fstype": parts[2]})
    return mounts


def parse_modules(text: str) -> List[str]:
    return sorted({line.split()[0] for line in text.splitlines() if line.strip()})


def parse_nvidia_params(text: str) -> Dict[str, str]:
    out = {}
    for line in text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def parse_acs(text: str) -> Dict[str, Any]:
    """Find PCIe bridges/switch ports with ACS request/completion redirect enabled."""
    enabled, seen, denied = [], 0, False
    dev = None
    for line in text.splitlines():
        m = re.match(r"^([0-9a-f]{2,4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]|[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]) (.*)", line)
        if m:
            dev = m.group(1)
            continue
        if "<access denied>" in line:
            denied = True
        if "ACSCtl:" in line:
            seen += 1
            if "ReqRedir+" in line or "CmpltRedir+" in line or "SrcValid+" in line:
                enabled.append(dev)
    return {"acs_capable_ports": seen, "acs_enabled": enabled, "access_denied": denied}


def parse_nccl_tests(text: str) -> Optional[float]:
    m = re.search(r"Avg bus bandwidth\s*:\s*([0-9.]+)", text)
    return float(m.group(1)) if m else None


def parse_ib_write_bw(text: str) -> Optional[float]:
    """Return average Gb/s from ``ib_write_bw --report_gbits`` output."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "BW average" in line:
            for row in lines[i + 1:]:
                cols = row.split()
                if len(cols) >= 4 and cols[0].isdigit():
                    try:
                        return float(cols[3])
                    except ValueError:
                        return None
    return None


def parse_dcgm_diag(text: str) -> Dict[str, Any]:
    fails, warns, passes = [], [], 0
    for line in text.splitlines():
        if "|" not in line:
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < 2:
            continue
        name, result = cols[0], cols[-1]
        if result.lower().startswith("fail"):
            fails.append(f"{name}: {result}")
        elif result.lower().startswith("warn"):
            warns.append(f"{name}: {result}")
        elif result.lower().startswith("pass"):
            passes += 1
    return {"passed": passes, "failed": fails, "warnings": warns}


def version_tuple(v: str) -> Tuple[int, ...]:
    parts = re.findall(r"\d+", v or "")
    return tuple(int(p) for p in parts[:4])


def version_ge(have: str, need: str) -> bool:
    a, b = version_tuple(have), version_tuple(need)
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) >= b + (0,) * (n - len(b))
