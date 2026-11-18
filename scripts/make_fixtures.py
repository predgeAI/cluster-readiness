#!/usr/bin/env python3
"""Regenerate the recorded node outputs used by tests and ``--demo``.

The fixtures are synthetic: they reproduce the exact output formats of
nvidia-smi, ibstat, dmesg, dcgmi, nccl-tests, ib_write_bw, scontrol and
friends, with values modelled on real HGX H100 and A40 nodes. Host names,
UUIDs, GUIDs and addresses are made up.

    python3 scripts/make_fixtures.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "src" / "predge_ready" / "fixtures"

H100_BUS = ["18", "2a", "3a", "5d", "9a", "ab", "ba", "db"]


def w(base: Path, rel: str, text: str) -> None:
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text if text.endswith("\n") or not text else text + "\n")


def gpu_row(i, name, bus, mem, drv, temp, sm, smax, pw, pl, ecc_u=0, ecc_c=0, mask="0x0000000000000001", retired="[N/A]", rpend="No", rfail="No", width=16, persist="Enabled"):
    uuid = f"GPU-{(0x5e7a1000 + i * 7919 + int(bus, 16)):08x}-1c2d-4e5f-8a9b-{i:02d}{bus}c0ffee00"
    base = f"{i}, {name}, {uuid}, 00000000:{bus.upper()}:00.0, {mem}, {drv}, {temp}, {sm}, {smax}, {pw:.2f}, {pl:.2f}, {persist}, 5, 5, {width}, 16, {ecc_u}, {ecc_c}"
    return base, f"{mask}, {retired}, {rpend}, {rfail}"


def nvidia_smi_header(drv, cuda):
    return (
        "+-----------------------------------------------------------------------------------------+\n"
        f"| NVIDIA-SMI {drv}             Driver Version: {drv}     CUDA Version: {cuda}     |\n"
        "|-----------------------------------------+------------------------+----------------------+\n"
    )


def ibstat(cas):
    out = []
    for ca, fw, state, phys, rate, layer in cas:
        guid = "0x" + format(0xA088C20300F1E000 + int(ca.split("_")[1]) * 17, "016x")
        out.append(
            f"CA '{ca}'\n\tCA type: MT4129\n\tNumber of ports: 1\n\tFirmware version: {fw}\n\tHardware version: 0\n"
            f"\tNode GUID: {guid}\n\tSystem image GUID: {guid}\n\tPort 1:\n\t\tState: {state}\n\t\tPhysical state: {phys}\n"
            f"\t\tRate: {rate}\n\t\tBase lid: {0 if layer == 'Ethernet' else 100 + int(ca.split('_')[1])}\n\t\tLMC: 0\n\t\tSM lid: {0 if layer == 'Ethernet' else 1}\n"
            f"\t\tCapability mask: 0xa751e848\n\t\tPort GUID: {guid}\n\t\tLink layer: {layer}\n"
        )
    return "".join(out)


def nvlink(n, name, inactive=()):
    out = []
    for g in range(n):
        out.append(f"GPU {g}: {name} (UUID: GPU-0000{g})")
        for link in range(18):
            out.append(f"\t Link {link}: <inactive>" if (g, link) in inactive else f"\t Link {link}: 26.562 GB/s")
    return "\n".join(out) + "\n"


MODULES_COMMON = """mlx5_ib 487424 0 - Live 0x0000000000000000
ib_uverbs 196608 2 nvidia_peermem,mlx5_ib, Live 0x0000000000000000
ib_core 507904 4 nvidia_peermem,mlx5_ib,ib_uverbs,ib_umad, Live 0x0000000000000000
mlx5_core 2420736 1 mlx5_ib, Live 0x0000000000000000
nvidia_uvm 4972544 0 - Live 0x0000000000000000
nvidia 99016704 120 nvidia_uvm,nvidia_peermem,nvidia_modeset, Live 0x0000000000000000
"""

DCGM_PASS = """Successfully ran diagnostic for group.
+---------------------------+------------------------------------------------+
| Diagnostic                | Result                                         |
+===========================+================================================+
|-----  Metadata  ----------+------------------------------------------------|
| DCGM Version              | 4.5.3                                          |
| Driver Version Detected   | 580.178.04                                     |
| GPU Device IDs Detected   | 2330,2330,2330,2330,2330,2330,2330,2330        |
|-----  Deployment  --------+------------------------------------------------|
| Denylist                  | Pass                                           |
| NVML Library              | Pass                                           |
| CUDA Main Library         | Pass                                           |
| Permissions and OS Blocks | Pass                                           |
| Persistence Mode          | Pass                                           |
| Environment Variables     | Pass                                           |
| Page Retirement/Row Remap | Pass                                           |
| Graphics Processes        | Pass                                           |
| Inforom                   | Pass                                           |
+-----  Integration  -------+------------------------------------------------+
| PCIe                      | Pass - All                                     |
+-----  Hardware  ----------+------------------------------------------------+
| GPU Memory                | Pass - All                                     |
| Diagnostic                | Pass - All                                     |
+-----  Stress  ------------+------------------------------------------------+
| Targeted Stress           | Pass - All                                     |
| Targeted Power            | Pass - All                                     |
| Memory Bandwidth          | Pass - All                                     |
+---------------------------+------------------------------------------------+
"""


def nccl_out(n, busbw):
    return (
        f"# nThread 1 nGpus {n} minBytes 8 maxBytes 4294967296 step: 2(factor) warmup iters: 5 iters: 20 agg iters: 1 validation: 1 graph: 0\n"
        "#\n#                                                              out-of-place                       in-place\n"
        "#       size         count      type   redop    root     time   algbw   busbw #wrong     time   algbw   busbw #wrong\n"
        f"  4294967296    1073741824     float     sum      -1  {4294967296 / (busbw * 1e9 * n / (2 * (n - 1))) * 1e6:9.0f}  {busbw * n / (2 * (n - 1)):6.2f}  {busbw:6.2f}      0\n"
        "# Out of bounds values : 0 OK\n"
        f"# Avg bus bandwidth    : {busbw}\n#\n"
    )


def ibbw_out(dev, bw):
    return (
        "---------------------------------------------------------------------------------------\n"
        "                    RDMA_Write BW Test\n"
        f" Dual-port       : OFF\t\tDevice         : {dev}\n"
        " Number of qps   : 1\t\tTransport type : IB\n"
        " Connection type : RC\t\tUsing SRQ      : OFF\n"
        " PCIe relax order: ON\n"
        " TX depth        : 128\n"
        " CQ Moderation   : 1\n"
        " Mtu             : 4096[B]\n"
        " Link type       : IB\n"
        "---------------------------------------------------------------------------------------\n"
        " #bytes     #iterations    BW peak[Gb/sec]    BW average[Gb/sec]   MsgRate[Mpps]\n"
        f" 65536      3747000          0.00               {bw:.2f} \t\t   0.748652\n"
        "---------------------------------------------------------------------------------------\n"
    )


def gemm_out(name, vals):
    rows = ", ".join(f'{{"gpu": {i}, "name": "{name}", "bf16": {v}, "fp16": {round(v * 1.01, 1)}}}' for i, v in enumerate(vals))
    return '{"results": [' + rows + "]}\n"


SCONTROL_HEALTHY = """Configuration data as of 2026-11-18T09:12:44
AccountingStorageType   = accounting_storage/slurmdbd
ClusterName             = gpu-prod
DefCpuPerGPU            = 24
DefMemPerGPU            = 245760
GresTypes               = gpu
HealthCheckInterval     = 60 sec
HealthCheckNodeState    = ANY
HealthCheckProgram      = /usr/local/sbin/predge-ready-hc
JobAcctGatherType       = jobacct_gather/cgroup
MpiDefault              = pmix
PlugStackConfig         = /etc/slurm/plugstack.conf
Prolog                  = /etc/slurm/prolog.d/*
ProctrackType           = proctrack/cgroup
SelectType              = select/cons_tres
SelectTypeParameters    = CR_CORE_MEMORY
SLURM_VERSION           = 25.05.6
TaskPlugin              = task/affinity,task/cgroup
TopologyPlugin          = topology/block
"""

SCONTROL_BROKEN = """Configuration data as of 2026-11-18T09:14:02
AccountingStorageType   = accounting_storage/slurmdbd
ClusterName             = gpu-prod
GresTypes               = gpu
HealthCheckInterval     = 0 sec
HealthCheckNodeState    = ANY
HealthCheckProgram      = (null)
JobAcctGatherType       = jobacct_gather/cgroup
MpiDefault              = none
PlugStackConfig         = /etc/slurm/plugstack.conf
ProctrackType           = proctrack/cgroup
SelectType              = select/cons_tres
SLURM_VERSION           = 24.05.4
TaskPlugin              = task/affinity,task/cgroup
TopologyPlugin          = topology/default
"""


def scontrol_node(name, gres, state, reason=None):
    r = f"\n   Reason={reason} [root@2026-11-18T08:01:12]" if reason else ""
    return (
        f"NodeName={name} Arch=x86_64 CoresPerSocket=56\n   CPUAlloc=0 CPUEfctv=224 CPUTot=224 CPULoad=0.41\n"
        f"   AvailableFeatures=(null)\n   ActiveFeatures=(null)\n   Gres={gres}\n   NodeAddr={name} NodeHostName={name} Version=25.05.6\n"
        f"   OS=Linux 6.8.0-87-generic #88-Ubuntu SMP\n   RealMemory=2063000 AllocMem=0 FreeMem=2011234 Sockets=2 Boards=1\n"
        f"   State={state} ThreadsPerCore=2 TmpDisk=0 Weights=1 Owner=N/A MCS_label=N/A\n   Partitions=gpu{r}\n"
    )


ACS_ROOT = """00:01.0 PCI bridge: Intel Corporation Device 09ab (rev 04) (prog-if 00 [Normal decode])
\tCapabilities: [220 v1] Access Control Services
\t\tACSCap:\tSrcValid+ TransBlk+ ReqRedir+ CmpltRedir+ UpstreamFwd+ EgressCtrl- DirectTrans-
\t\tACSCtl:\tSrcValid- TransBlk- ReqRedir- CmpltRedir- UpstreamFwd- EgressCtrl- DirectTrans-
15:00.0 PCI bridge: Broadcom / LSI PEX890xx PCIe Gen 5 Switch (rev b0) (prog-if 00 [Normal decode])
\tCapabilities: [1d4 v1] Access Control Services
\t\tACSCap:\tSrcValid+ TransBlk+ ReqRedir+ CmpltRedir+ UpstreamFwd+ EgressCtrl+ DirectTrans+
\t\tACSCtl:\tSrcValid- TransBlk- ReqRedir- CmpltRedir- UpstreamFwd- EgressCtrl- DirectTrans-
16:01.0 PCI bridge: Broadcom / LSI PEX890xx PCIe Gen 5 Switch (rev b0) (prog-if 00 [Normal decode])
\tCapabilities: [1d4 v1] Access Control Services
\t\tACSCap:\tSrcValid+ TransBlk+ ReqRedir+ CmpltRedir+ UpstreamFwd+ EgressCtrl+ DirectTrans+
\t\tACSCtl:\tSrcValid- TransBlk- ReqRedir- CmpltRedir- UpstreamFwd- EgressCtrl- DirectTrans-
18:00.0 3D controller: NVIDIA Corporation GH100 [H100 SXM5 80GB] (rev a1)
\tSubsystem: NVIDIA Corporation Device 16c1
"""

ACS_DENIED = """00:01.0 PCI bridge: Intel Corporation Device 09ab (rev 04) (prog-if 00 [Normal decode])
\tCapabilities: <access denied>
17:00.0 3D controller: NVIDIA Corporation GA102GL [A40] (rev a1)
\tCapabilities: <access denied>
"""

DMESG_HEALTHY = """[    0.000000] Linux version 6.8.0-87-generic (buildd@lcy02-amd64-031) (x86_64-linux-gnu-gcc-12) #88-Ubuntu SMP PREEMPT_DYNAMIC
[   14.912331] nvidia: loading out-of-tree module taints kernel.
[   15.102114] nvidia-nvlink: Nvlink Core is being initialized, major device number 509
[   15.633870] NVRM: loading NVIDIA UNIX Open Kernel Module for x86_64  580.178.04  Release Build
[   18.204561] mlx5_core 0000:1a:00.0: mlx5_pcie_event:301:(pid 1210): PCIe slot advertised sufficient power (75W).
[   22.771045] nvidia-fabricmanager: initialized
[   31.004412] ib_srpt MAD registration failed for mlx5_8-1.
"""

DMESG_BROKEN = """[    0.000000] Linux version 6.5.0-41-generic (buildd@lcy02-amd64-108) #41~22.04.2-Ubuntu SMP PREEMPT_DYNAMIC
[   15.318820] NVRM: loading NVIDIA UNIX x86_64 Kernel Module  535.183.01  Sun May 12 19:39:15 UTC 2024
[ 5012.118233] NVRM: Xid (PCI:0000:3a:00): 48, pid=48213, name=python3, An uncorrectable double bit error (DBE) has been detected on GPU in the framebuffer at partition 6, subpartition 0.
[ 5012.120011] NVRM: Xid (PCI:0000:3a:00): 63, pid=48213, name=python3, Row Remapping Event: Row remapped successfully.
[ 6230.901112] mlx5_core 0000:9d:00.0: mlx5_port_module_event:1157:(pid 0): Port module event: module 0, Cable unplugged
[ 6231.004318] mlx5_core 0000:9d:00.0 ibp157s0: Link down
[ 8123.442101] NVRM: Xid (PCI:0000:9a:00): 79, pid='<unknown>', name=<unknown>, GPU has fallen off the bus.
[ 8123.442180] NVRM: GPU 0000:9a:00.0: GPU has fallen off the bus.
[ 8123.442201] NVRM: A GPU crash dump has been created. If possible, please run
               NVRM: nvidia-bug-report.sh as root to collect this data before
               NVRM: the NVIDIA kernel module is unloaded.
[ 8301.551904] nvidia-nvswitch2: SXid (PCI:0000:07:00.0): 12028, Non-fatal, Link 32 egress non-posted PRIV error (First)
"""

JOURNAL_A40 = """2026-11-18T03:12:01+0000 gpu-a40-03 kernel: NVRM: loading NVIDIA UNIX x86_64 Kernel Module  550.127.05  Tue Oct  8 03:22:07 UTC 2024
2026-11-18T07:44:19+0000 gpu-a40-03 kernel: NVRM: Xid (PCI:0000:17:00): 13, pid=88120, name=python, Graphics Exception: ESR 0x404600=0x80000010
"""

PS_HEALTHY = """systemd /sbin/init
slurmd /usr/sbin/slurmd --systemd
nv-hostengine /usr/bin/nv-hostengine -n --service-account nvidia-dcgm
dcgm-exporter /usr/bin/dcgm-exporter -f /etc/dcgm-exporter/dcp-metrics-included.csv
node_exporter /usr/local/bin/node_exporter --collector.textfile.directory=/var/lib/node_exporter/textfile_collector
ipmi_exporter /usr/local/bin/ipmi_exporter --config.file=/etc/ipmi_exporter.yml
nvidia-persistenced /usr/bin/nvidia-persistenced --user nvidia-persistenced
nv-fabricmanager /usr/bin/nv-fabricmanager -c /usr/share/nvidia/nvswitch/fabricmanager.cfg
promtail /usr/local/bin/promtail -config.file=/etc/promtail/config.yml
"""

PS_BROKEN = """systemd /sbin/init
slurmd /usr/sbin/slurmd --systemd
node_exporter /usr/local/bin/node_exporter
nv-fabricmanager /usr/bin/nv-fabricmanager -c /usr/share/nvidia/nvswitch/fabricmanager.cfg
"""

PS_A40 = """systemd /sbin/init
slurmd /usr/sbin/slurmd --systemd
"""

UNITS_HEALTHY = """slurmd.service loaded active running Slurm node daemon
nvidia-dcgm.service loaded active running NVIDIA DCGM service
nvidia-fabricmanager.service loaded active running NVIDIA fabric manager service
nvidia-persistenced.service loaded active running NVIDIA Persistence Daemon
predge-ready-health.timer loaded active waiting Run predge-ready health every minute
"""

LDCONFIG_FULL = """\t1342 libs found in cache `/etc/ld.so.cache'
\tlibnccl.so.2 (libc6,x86-64) => /usr/lib/x86_64-linux-gnu/libnccl.so.2
\tlibgdrapi.so.2 (libc6,x86-64) => /usr/lib/x86_64-linux-gnu/libgdrapi.so.2
\tlibcudart.so.13 (libc6,x86-64) => /usr/local/cuda/lib64/libcudart.so.13
"""


def healthy_h100(name: str, seed: int) -> Path:
    d = OUT / name
    drv = "580.178.04"
    base_rows, extra_rows = [], []
    for i, bus in enumerate(H100_BUS):
        b, e = gpu_row(i, "NVIDIA H100 80GB HBM3", bus, 81559, drv, 31 + (i + seed) % 6, 345, 1980, 69.5 + i * 0.7, 700.0)
        base_rows.append(b)
        extra_rows.append(e)
    w(d, "commands/gpu_query.txt", "\n".join(f"{b}, {e}" for b, e in zip(base_rows, extra_rows)))
    w(d, "commands/hostname.txt", name)
    w(d, "commands/uname.txt", "6.8.0-87-generic")
    w(d, "files/etc/os-release", 'PRETTY_NAME="Ubuntu 24.04.3 LTS"\nNAME="Ubuntu"\nVERSION_ID="24.04"')
    w(d, "commands/nvidia_smi.txt", nvidia_smi_header(drv, "13.0"))
    w(d, "commands/lspci_nvidia.txt", "\n".join(
        [f"{bus}:00.0 3D controller [0302]: NVIDIA Corporation GH100 [H100 SXM5 80GB] [10de:2330] (rev a1)" for bus in H100_BUS]
        + [f"0{k}:00.0 Bridge [0680]: NVIDIA Corporation GH100 [H100 NVSwitch] [10de:22a3] (rev a1)" for k in range(5, 9)]))
    w(d, "commands/nvlink.txt", nvlink(8, "NVIDIA H100 80GB HBM3"))
    w(d, "commands/fabricmanager.txt", "active")
    w(d, "commands/dmesg.txt", DMESG_HEALTHY)
    cas = [(f"mlx5_{k}", "28.47.1088", "Active", "LinkUp", 400, "InfiniBand") for k in range(8)]
    cas += [("mlx5_8", "28.47.1088", "Active", "LinkUp", 200, "Ethernet"), ("mlx5_9", "28.47.1088", "Active", "LinkUp", 200, "Ethernet")]
    w(d, "commands/ibstat.txt", ibstat(cas))
    w(d, "commands/pkeys.txt", "\n".join(
        f"/sys/class/infiniband/mlx5_{k}/ports/1/pkeys/{j}:{v}" for k in range(8) for j, v in ((0, "0xffff"), (1, "0x8012"))))
    w(d, "files/proc/modules", MODULES_COMMON + "nvidia_peermem 16384 0 - Live 0x0000000000000000\ngdrdrv 24576 0 - Live 0x0000000000000000\n")
    w(d, "files/proc/driver/nvidia/version", f"NVRM version: NVIDIA UNIX Open Kernel Module for x86_64  {drv}  Release Build  (dvs-builder@U22-I3-AF03-09-1)  Thu Oct 23 05:12:44 UTC 2026\nGCC version:  gcc version 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04)")
    w(d, "files/proc/driver/nvidia/params", "ResmanDebugLevel: 4294967295\nRmProfilingAdminOnly: 0\nEnableGpuFirmware: 18\nNVreg_OpenRmEnableUnsupportedGpus: 1")
    w(d, "commands/lspci_acs.txt", ACS_ROOT)
    w(d, "root", "")
    w(d, "commands/docker.txt", "Docker version 29.9.2, build 6c2cd5b")
    w(d, "commands/nvidia_ctk.txt", "NVIDIA Container Toolkit CLI version 1.19.1\ncommit: 4fa3b4a10fe6ad9d2a51c3bf37f6127a8e4c06a1")
    w(d, "commands/enroot.txt", "3.5.0")
    w(d, "commands/apptainer.txt", "apptainer version 1.4.1")
    w(d, "commands/plugstack.txt", "required /usr/local/lib/slurm/spank_pyxis.so runtime_path=/run/pyxis")
    w(d, "commands/scontrol_config.txt", SCONTROL_HEALTHY)
    w(d, "commands/scontrol_node.txt", scontrol_node(name, "gpu:h100:8(S:0-1)", "IDLE"))
    w(d, "files/proc/mounts", "sysfs /sys sysfs rw,nosuid,nodev,noexec,relatime 0 0\n/dev/nvme0n1p2 / ext4 rw,relatime 0 0\n10.40.0.10:/home /home nfs4 rw,relatime,vers=4.2,rsize=1048576,wsize=1048576 0 0\nwekafs-0 /mnt/weka wekafs rw,relatime,writecache,readcache_mode=on 0 0")
    w(d, "commands/statfs.txt", '  File: "/home"\n    ID: 0        Namelen: 255     Type: nfs\nBlock size: 1048576    Fundamental block size: 1048576')
    w(d, "commands/ps.txt", PS_HEALTHY)
    w(d, "commands/units.txt", UNITS_HEALTHY)
    w(d, "files/etc/nccl.conf", "NCCL_SOCKET_IFNAME=bond0\nNCCL_IB_HCA=mlx5_0,mlx5_1,mlx5_2,mlx5_3,mlx5_4,mlx5_5,mlx5_6,mlx5_7\n")
    w(d, "files/proc/sys/kernel/perf_event_paranoid", "1")
    w(d, "files/proc/sys/kernel/kptr_restrict", "0")
    w(d, "commands/nvcc.txt", "nvcc: NVIDIA (R) Cuda compiler driver\nCopyright (c) 2005-2026 NVIDIA Corporation\nCuda compilation tools, release 13.1, V13.1.80")
    w(d, "files/opt/hpcx/README", "HPC-X 2.24")
    w(d, "files/usr/share/lmod/lmod/README", "Lmod 8.7")
    w(d, "commands/ldconfig.txt", LDCONFIG_FULL)
    w(d, "commands/dcgmi_version.txt", "dcgmi  version: 4.5.3")
    # active
    w(d, "commands/dcgm_diag.txt", DCGM_PASS)
    w(d, "commands/nccl_allreduce.txt", nccl_out(8, 478.31 - seed * 3.2))
    w(d, "commands/ib_write_bw.txt", ibbw_out("mlx5_1", 392.51 - seed))
    w(d, "commands/gemm.txt", gemm_out("NVIDIA H100 80GB HBM3", [742.1, 738.9, 745.6, 740.2, 736.4, 744.8, 739.7, 741.3]))
    w(d, "tools.txt", "\n".join([
        "hostname", "uname", "nvidia-smi", "lspci", "systemctl", "dmesg", "journalctl", "ibstat", "sh", "docker", "nvidia-ctk",
        "enroot", "apptainer", "scontrol", "sinfo", "slurmd", "stat", "ps", "nvcc", "ldconfig", "dcgmi", "all_reduce_perf",
        "ib_write_bw", "python3",
    ]))
    return d


def broken_h100() -> Path:
    name = "gpu-h100-07"
    d = OUT / name
    drv = "535.183.01"
    rows = []
    extras = []
    for i, bus in enumerate(H100_BUS):
        if bus == "9a":
            continue  # fell off the bus: lspci still sees it, nvidia-smi does not
        idx = len(rows)
        kw = {}
        if bus == "3a":
            kw = dict(ecc_u=2, ecc_c=14, rpend="Yes")
        if bus == "ba":
            kw = dict(mask="0x0000000000000048")
        temp = 91 if bus == "ba" else 38 + idx
        sm = 1095 if bus == "ba" else 1980
        b, e = gpu_row(idx, "NVIDIA H100 80GB HBM3", bus, 81559, drv, temp, sm, 1980, 410.0 if bus == "ba" else 312.0, 700.0, **kw)
        rows.append(b)
        extras.append(e.split(", "))
    w(d, "commands/gpu_query.txt", 'Field "clocks_event_reasons.active" is not a valid field to query.')
    w(d, "commands/gpu_query.rc", "2")
    w(d, "commands/gpu_query_base.txt", "\n".join(rows))
    w(d, "commands/gpu_query_clocks_event_reasons_active.txt", 'Field "clocks_event_reasons.active" is not a valid field to query.')
    w(d, "commands/gpu_query_clocks_event_reasons_active.rc", "2")
    w(d, "commands/gpu_query_clocks_throttle_reasons_active.txt", "\n".join(x[0] for x in extras))
    w(d, "commands/gpu_query_retired_pages_pending.txt", "\n".join(x[1] for x in extras))
    w(d, "commands/gpu_query_remapped_rows_pending.txt", "\n".join(x[2] for x in extras))
    w(d, "commands/gpu_query_remapped_rows_failure.txt", "\n".join(x[3] for x in extras))
    w(d, "commands/hostname.txt", name)
    w(d, "commands/uname.txt", "6.5.0-41-generic")
    w(d, "files/etc/os-release", 'PRETTY_NAME="Ubuntu 22.04.4 LTS"\nNAME="Ubuntu"\nVERSION_ID="22.04"')
    w(d, "commands/nvidia_smi.txt", nvidia_smi_header(drv, "12.2"))
    w(d, "commands/lspci_nvidia.txt", "\n".join(
        [f"{bus}:00.0 3D controller [0302]: NVIDIA Corporation GH100 [H100 SXM5 80GB] [10de:2330] (rev a1)" for bus in H100_BUS]
        + [f"0{k}:00.0 Bridge [0680]: NVIDIA Corporation GH100 [H100 NVSwitch] [10de:22a3] (rev a1)" for k in range(5, 9)]))
    w(d, "commands/nvlink.txt", nvlink(7, "NVIDIA H100 80GB HBM3", inactive={(2, 4), (2, 5), (2, 6), (2, 7)}))
    w(d, "commands/fabricmanager.txt", "active")
    w(d, "commands/dmesg.txt", DMESG_BROKEN)
    cas = [(f"mlx5_{k}", "28.39.1002", "Down" if k == 4 else "Active", "Polling" if k == 4 else "LinkUp", 400, "InfiniBand") for k in range(8)]
    cas += [("mlx5_8", "28.39.1002", "Active", "LinkUp", 200, "Ethernet")]
    w(d, "commands/ibstat.txt", ibstat(cas))
    w(d, "commands/pkeys.txt", "\n".join(f"/sys/class/infiniband/mlx5_{k}/ports/1/pkeys/0:0xffff" for k in range(8)))
    w(d, "files/proc/modules", MODULES_COMMON + "nvidia_peermem 16384 0 - Live 0x0000000000000000\n")
    w(d, "files/proc/driver/nvidia/version", f"NVRM version: NVIDIA UNIX x86_64 Kernel Module  {drv}  Sun May 12 19:39:15 UTC 2024\nGCC version:  gcc version 12.3.0 (Ubuntu 12.3.0-1ubuntu1~22.04)")
    w(d, "files/proc/driver/nvidia/params", "ResmanDebugLevel: 4294967295\nRmProfilingAdminOnly: 1\nEnableGpuFirmware: 18")
    w(d, "commands/lspci_acs.txt", ACS_DENIED)
    w(d, "commands/nvidia_ctk.txt", "NVIDIA Container Toolkit CLI version 1.16.1\ncommit: a470818ba7d9166be282cd0039dd2fc9b0a34d73")
    w(d, "commands/enroot.txt", "3.4.1")
    w(d, "commands/plugstack.txt", "required /usr/local/lib/slurm/spank_pyxis.so")
    w(d, "commands/scontrol_config.txt", SCONTROL_BROKEN)
    w(d, "commands/scontrol_node.txt", scontrol_node(name, "gpu:h100:8(S:0-1)", "MIXED"))
    w(d, "files/proc/mounts", "/dev/nvme0n1p2 / ext4 rw,relatime 0 0\n10.40.0.10:/home /home nfs4 rw,relatime,vers=4.2 0 0\nwekafs-0 /mnt/weka wekafs rw,relatime,writecache 0 0")
    w(d, "commands/statfs.txt", '  File: "/home"\n    ID: 0        Namelen: 255     Type: nfs')
    w(d, "commands/ps.txt", PS_BROKEN)
    w(d, "commands/units.txt", "slurmd.service loaded active running Slurm node daemon\nnvidia-fabricmanager.service loaded active running NVIDIA fabric manager service\n")
    w(d, "files/etc/nccl.conf", "NCCL_IB_HCA=mlx5\nNCCL_PROTO=Simple\nNCCL_MIN_NCHANNELS=32\n")
    w(d, "files/proc/sys/kernel/perf_event_paranoid", "4")
    w(d, "files/proc/sys/kernel/kptr_restrict", "1")
    w(d, "commands/nvcc.txt", "Cuda compilation tools, release 12.2, V12.2.140")
    w(d, "commands/ldconfig.txt", "\tlibnccl.so.2 (libc6,x86-64) => /usr/lib/x86_64-linux-gnu/libnccl.so.2\n")
    fail_diag = DCGM_PASS.replace("| GPU Memory                | Pass - All                                     |",
                                  "| GPU Memory                | Fail - GPU: 2                                  |").replace(
        "| Targeted Power            | Pass - All                                     |",
        "| Targeted Power            | Warn - GPU: 5                                  |").replace("580.178.04", drv)
    w(d, "commands/dcgm_diag.txt", fail_diag)
    w(d, "commands/dcgm_diag.rc", "0")
    w(d, "commands/dcgmi_version.txt", "dcgmi  version: 3.3.6")
    w(d, "commands/nccl_allreduce.txt", nccl_out(7, 141.2))
    w(d, "commands/ib_write_bw.txt", ibbw_out("mlx5_1", 371.9))
    w(d, "commands/gemm.txt", gemm_out("NVIDIA H100 80GB HBM3", [738.2, 741.0, 702.3, 739.5, 744.1, 412.6, 736.8]))
    w(d, "tools.txt", "\n".join([
        "hostname", "uname", "nvidia-smi", "lspci", "systemctl", "dmesg", "journalctl", "ibstat", "sh", "nvidia-ctk", "enroot",
        "scontrol", "sinfo", "slurmd", "stat", "ps", "nvcc", "ldconfig", "dcgmi", "all_reduce_perf", "ib_write_bw", "python3",
    ]))
    return d


def a40() -> Path:
    name = "gpu-a40-03"
    d = OUT / name
    drv = "550.127.05"
    buses = ["17", "31", "4b", "65", "98", "b1", "ca", "e3"]
    rows = []
    for i, bus in enumerate(buses):
        b, e = gpu_row(i, "NVIDIA A40", bus, 46068, drv, 29 + i, 210, 1740, 31.0 + i, 300.0, retired="No", rpend="No")
        rows.append(f"{b}, {e}")
    w(d, "commands/gpu_query.txt", "\n".join(rows))
    w(d, "commands/hostname.txt", name)
    w(d, "commands/uname.txt", "5.15.0-125-generic")
    w(d, "files/etc/os-release", 'PRETTY_NAME="Ubuntu 22.04.5 LTS"\nNAME="Ubuntu"\nVERSION_ID="22.04"')
    w(d, "commands/nvidia_smi.txt", nvidia_smi_header(drv, "12.4"))
    w(d, "commands/lspci_nvidia.txt", "\n".join(f"{bus}:00.0 3D controller [0302]: NVIDIA Corporation GA102GL [A40] [10de:2235] (rev a1)" for bus in buses))
    w(d, "commands/nvlink.txt", "")
    w(d, "commands/fabricmanager.txt", "inactive")
    w(d, "commands/fabricmanager.rc", "3")
    w(d, "commands/dmesg.txt", "dmesg: read kernel buffer failed: Operation not permitted")
    w(d, "commands/dmesg.rc", "1")
    w(d, "commands/journal_kernel.txt", JOURNAL_A40)
    cas = [("mlx5_0", "22.41.1000", "Active", "LinkUp", 200, "InfiniBand"), ("mlx5_1", "22.41.1000", "Active", "LinkUp", 200, "InfiniBand")]
    w(d, "commands/ibstat.txt", ibstat(cas))
    w(d, "commands/pkeys.txt", "/sys/class/infiniband/mlx5_0/ports/1/pkeys/0:0xffff\n/sys/class/infiniband/mlx5_1/ports/1/pkeys/0:0xffff")
    w(d, "files/proc/modules", MODULES_COMMON.replace("nvidia_peermem,", ""))
    w(d, "files/proc/driver/nvidia/version", f"NVRM version: NVIDIA UNIX x86_64 Kernel Module  {drv}  Tue Oct  8 03:22:07 UTC 2024")
    w(d, "files/proc/driver/nvidia/params", "RmProfilingAdminOnly: 1")
    w(d, "commands/lspci_acs.txt", ACS_DENIED)
    w(d, "commands/nvidia_container_cli.txt", "cli-version: 1.17.3\nlib-version: 1.17.3")
    w(d, "commands/scontrol_config.txt", SCONTROL_BROKEN)
    w(d, "commands/scontrol_node.txt", scontrol_node(name, "(null)", "IDLE"))
    w(d, "files/proc/mounts", "/dev/sda2 / ext4 rw,relatime 0 0\n10.40.0.10:/home /home nfs4 rw,relatime,vers=4.2 0 0")
    w(d, "commands/statfs.txt", '  File: "/home"\n    ID: 0        Namelen: 255     Type: nfs')
    w(d, "commands/ps.txt", PS_A40)
    w(d, "commands/units.txt", "slurmd.service loaded active running Slurm node daemon\n")
    w(d, "files/proc/sys/kernel/perf_event_paranoid", "2")
    w(d, "files/proc/sys/kernel/kptr_restrict", "1")
    w(d, "commands/ldconfig.txt", "\tlibcudart.so.12 (libc6,x86-64) => /usr/local/cuda/lib64/libcudart.so.12\n")
    w(d, "commands/nccl_allreduce.txt", nccl_out(8, 21.4))
    w(d, "commands/ib_write_bw.txt", ibbw_out("mlx5_1", 188.3))
    w(d, "commands/gemm.txt", gemm_out("NVIDIA A40", [111.8, 112.4, 110.9, 112.0, 111.5, 112.2, 111.1, 110.6]))
    w(d, "tools.txt", "\n".join([
        "hostname", "uname", "nvidia-smi", "lspci", "systemctl", "dmesg", "journalctl", "ibstat", "sh", "nvidia-container-cli",
        "scontrol", "sinfo", "slurmd", "stat", "ps", "ldconfig", "all_reduce_perf", "ib_write_bw", "python3",
    ]))
    return d


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    healthy_h100("gpu-h100-01", 0)
    healthy_h100("gpu-h100-02", 1)
    broken_h100()
    a40()
    (OUT / "__init__.py").write_text("")
    print(f"fixtures written to {OUT}")


if __name__ == "__main__":
    main()
