"""Optional active tests (``--active``). Each runs only if its tool exists.

These put real load on the node. Run them on idle or drained nodes only.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from . import parsers as P
from .runner import Runner

GEMM_SCRIPT = r"""
import json, time
try:
    import torch
except Exception as e:
    print(json.dumps({"error": "torch not importable: %s" % e})); raise SystemExit(0)
if not torch.cuda.is_available():
    print(json.dumps({"error": "torch.cuda not available"})); raise SystemExit(0)
res = []
n = 8192
for i in range(torch.cuda.device_count()):
    dev = torch.device("cuda", i)
    row = {"gpu": i, "name": torch.cuda.get_device_name(i)}
    for label, dt in (("bf16", torch.bfloat16), ("fp16", torch.float16)):
        a = torch.randn(n, n, device=dev, dtype=dt); b = torch.randn(n, n, device=dev, dtype=dt)
        for _ in range(3): a @ b
        torch.cuda.synchronize(dev)
        iters = 20; t = time.time()
        for _ in range(iters): a @ b
        torch.cuda.synchronize(dev)
        row[label] = round(2 * n ** 3 * iters / (time.time() - t) / 1e12, 1)
    res.append(row)
print(json.dumps({"results": res}))
"""

# Conservative dense bf16 TFLOP/s floors for an 8192^3 GEMM (roughly 60% of the
# datasheet dense peak). A GPU below the floor is worth a closer look; it is not
# a precise acceptance threshold.
GEMM_FLOORS = {"B300": 1350, "B200": 1350, "H200": 590, "H100": 590, "H800": 590, "A100": 185, "L40S": 210, "A40": 85, "L40": 105}

# Single-node all_reduce bus bandwidth floors in GB/s (8 GPUs over NVLink/NVSwitch).
NCCL_FLOORS = {"B300": 600, "B200": 600, "H200": 350, "H100": 350, "H800": 160, "A100": 200}


def model_key(name: str, table: Dict[str, float]) -> str:
    for k in table:
        if k.lower() in (name or "").lower():
            return k
    return ""


def run_active(r: Runner, facts: Dict[str, Any], opts: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    gpus = facts.get("gpu", {}).get("gpus") or []
    n = len(gpus)
    name = gpus[0]["name"] if gpus else ""

    level = str(opts.get("diag_level", 3))
    res = r.run("dcgm_diag", ["dcgmi", "diag", "-r", level], float(opts.get("diag_timeout", 2400)))
    if res.missing:
        out["dcgm_diag"] = {"reason": "dcgmi not installed (install DCGM)"}
    elif res.timed_out:
        out["dcgm_diag"] = {"reason": "dcgmi diag timed out"}
    else:
        parsed = P.parse_dcgm_diag(res.out or res.err)
        parsed["level"] = int(level)
        parsed["rc"] = res.rc
        out["dcgm_diag"] = parsed

    if n:
        bin_ = opts.get("nccl_tests_bin") or "all_reduce_perf"
        res = r.run("nccl_allreduce", [bin_, "-b", "8", "-e", "4G", "-f", "2", "-g", str(n)], 900)
        if res.missing:
            out["nccl_allreduce"] = {"reason": "nccl-tests all_reduce_perf not found (build github.com/NVIDIA/nccl-tests, or pass --nccl-tests-bin)"}
        else:
            bw = P.parse_nccl_tests(res.out)
            key = model_key(name, NCCL_FLOORS)
            out["nccl_allreduce"] = {"busbw_gbs": bw, "gpus": n, "floor_gbs": NCCL_FLOORS.get(key) if n >= 8 else None, "rc": res.rc}

        res = r.run("gemm", [opts.get("python") or "python3", "-c", GEMM_SCRIPT], 600)
        if res.missing:
            out["gemm"] = {"reason": "python3 not found"}
        else:
            try:
                data = json.loads(res.out.strip().splitlines()[-1])
            except (ValueError, IndexError):
                data = {"error": "unexpected output"}
            if "results" in data:
                key = model_key(name, GEMM_FLOORS)
                data["floor_bf16"] = GEMM_FLOORS.get(key)
            out["gemm"] = data
    else:
        out["nccl_allreduce"] = {"reason": "no GPUs visible"}
        out["gemm"] = {"reason": "no GPUs visible"}

    ports = [p for p in (facts.get("ib") or {}).get("ports") or [] if p.get("state", "").lower() == "active"]
    if len(ports) >= 2:
        a, b = ports[0]["ca"], ports[1]["ca"]
        script = (
            f"ib_write_bw -d {a} -F --report_gbits -D 5 >/dev/null 2>&1 & sleep 2; "
            f"ib_write_bw -d {b} -F --report_gbits -D 5 127.0.0.1; wait"
        )
        if not r.which("ib_write_bw"):
            out["ib_write_bw"] = {"reason": "ib_write_bw not installed (perftest package)"}
        else:
            res = r.run("ib_write_bw", ["sh", "-c", script], 60)
            bw = P.parse_ib_write_bw(res.out)
            rate = ports[1].get("rate")
            out["ib_write_bw"] = {"pair": f"{a}->{b}", "gbps": bw, "port_rate_gbps": rate, "rc": res.rc}
    else:
        out["ib_write_bw"] = {"reason": "needs two active RDMA ports on this node"}
    return out
