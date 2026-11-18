# Cluster readiness report: gpu-prod

> Independent readiness estimate against the published ClusterMAX criteria. Not a SemiAnalysis rating and not affiliated with SemiAnalysis; ClusterMAX is a SemiAnalysis trademark.

Generated 2026-11-18T12:00:00Z by predge-ready 0.1.0 (demo:broken (recorded fixture outputs, not a live cluster)). Nodes scanned: 3.
Expected: gpu=H100, count=8, ib=8.

## Summary

- Readiness index (all 143 criteria, Unknown = 0): **21.7%**
- Index over the 55 criteria this scan could evidence: **56.4%**
- Meets 10 · Partial 42 · Gap 3 · Unknown 88
- Node health: 1 healthy, 0 warning, 2 failing

## Top fixes

1. **Drain and repair 2 failing node(s)** (Fail). gpu-h100-07: 7 GPUs visible to nvidia-smi, 8 expected (lspci sees more: a GPU has likely fallen off the bus); XID 48 on 0000:3a:00 (Double-bit ECC error); XID 79 on 0000:9a:00 (GPU has fallen off the bus); Uncorrectable (volatile) ECC errors on GPU 2; 1 InfiniBand port(s) not Active: mlx5_4/1 Down/Polling; 4 of 126 NVLink links inactive | gpu-a40-03: 2 active fast ports, 8 expected; Node reports NVIDIA A40 but H100 was expected. Keep them out of the scheduler until predge-ready health passes. Criteria: LIF-4, MON-3, MON-5, MON-7, REL-10, REL-13, REL-15, REL-16, REL-21, REL-4, REL-6, REL-7, REL-8, REL-9. Nodes: gpu-h100-07, gpu-a40-03.
2. **NVIDIA Container Toolkit patched** (Fail). Upgrade nvidia-container-toolkit to 1.19.1+ on every node. Criteria: SEC-14, SEC-15, SEC-16. Nodes: gpu-h100-07, gpu-a40-03.
3. **Failing nodes are drained automatically** (Fail). Install predge-ready health --drain as Slurm HealthCheckProgram or a systemd timer (see docs/health-checks.md). Criteria: MON-3, MON-8, REL-25. Nodes: gpu-h100-07, gpu-a40-03.
4. **GPU and node metrics exporters running** (Fail). Run dcgm-exporter and node-exporter on every GPU node and scrape them into Prometheus/Grafana. Criteria: MON-10, MON-14, MON-2, REL-17. Nodes: gpu-h100-07, gpu-a40-03.
5. **Slurm HealthCheckProgram configured** (Fail). Set HealthCheckProgram to a GPU-aware check (e.g. predge-ready health --drain) with HealthCheckInterval=60. Criteria: MON-16, MON-3, MON-6. Nodes: gpu-h100-07, gpu-a40-03.
6. **Latest-generation GPUs on this node** (Fail). Plan B200/B300/GB300 (or MI355X) capacity and publish the timeline. Criteria: AVA-1, AVA-7. Nodes: gpu-h100-01, gpu-h100-07, gpu-a40-03.
7. **NVIDIA driver at or above the published security minimum** (Fail). Upgrade the NVIDIA driver to 535.309.01 or newer (https://nvidia.custhelp.com/app/answers/detail/a_id/5861/). Criteria: SEC-17. Nodes: gpu-h100-07, gpu-a40-03.
8. **GPUDirect RDMA path available (dma_buf or nvidia_peermem)** (Fail). Install the open kernel module (or load nvidia_peermem) so NCCL can use GPUDirect RDMA. Criteria: LIF-8. Nodes: gpu-h100-07, gpu-a40-03.
9. **ncu hardware counters available to non-root users** (Fail). Set options nvidia NVreg_RestrictProfilingToAdminUsers=0 in /etc/modprobe.d and reload the driver. Criteria: MON-1. Nodes: gpu-h100-07, gpu-a40-03.
10. **Same PKeys on every node** (Fail). Fix partition membership in the subnet manager. Criteria: REL-23.

## Categories

| Category | Rows | Meets | Partial | Gap | Unknown | Index |
|---|---|---|---|---|---|---|
| Security | 20 | 0 | 5 | 0 | 15 | 12.5% |
| Lifecycle | 15 | 1 | 2 | 0 | 12 | 13.3% |
| Orchestration | 6 | 0 | 1 | 0 | 5 | 8.3% |
| Orchestration: Slurm | 7 | 0 | 3 | 0 | 4 | 21.4% |
| Orchestration: Kubernetes | 5 | 0 | 0 | 0 | 5 | 0.0% |
| Storage | 16 | 1 | 1 | 0 | 14 | 9.4% |
| Networking | 10 | 3 | 3 | 0 | 4 | 45.0% |
| Reliability and health checks | 25 | 4 | 15 | 1 | 5 | 46.0% |
| Monitoring | 16 | 1 | 11 | 0 | 4 | 40.6% |
| Pricing and billing | 7 | 0 | 0 | 0 | 7 | 0.0% |
| Partnerships | 6 | 0 | 0 | 0 | 6 | 0.0% |
| Availability and support | 10 | 0 | 1 | 2 | 7 | 5.0% |

## Node checks

| Check | Status | Nodes affected | Detail | Criteria |
|---|---|---|---|---|
| All GPUs visible to the driver | Fail | gpu-h100-07 | 7 GPUs visible to nvidia-smi, 8 expected (lspci sees more: a GPU has likely fallen off the bus) | REL-4 |
| GPU model matches what was sold | Fail | gpu-a40-03 | Node reports NVIDIA A40 but H100 was expected | LIF-4 |
| Latest-generation GPUs on this node | Fail | gpu-h100-01, gpu-h100-07, gpu-a40-03 | not a current training GPU | AVA-1, AVA-7 |
| GPU is a current model (H100/H200/A100/L40S/MI300X or newer) | Warn | gpu-a40-03 | Model is not in the ClusterMAX current-model list | AVA-2 |
| NVIDIA driver at or above the published security minimum | Fail | gpu-h100-07, gpu-a40-03 | Driver 535.183.01 is below 535.309.01 for its branch | SEC-17 |
| Persistence mode enabled | Pass |  |  | LIF-9 |
| No hardware clock throttling | Fail | gpu-h100-07 | Hardware slowdown active: GPU5: HwSlowdown,HwThermalSlowdown | REL-16, REL-7 |
| GPU temperatures within limits | Fail | gpu-h100-07 | GPU temperature at or above 87 C on GPU 5 | REL-16, REL-7 |
| No uncorrectable ECC errors | Fail | gpu-h100-07 | Uncorrectable (volatile) ECC errors on GPU 2 | REL-15, REL-8 |
| No pending page retirement / row remapping | Warn | gpu-h100-07 | Reset pending on GPU 2 | REL-15, REL-8 |
| GPU PCIe link at full width | Pass |  | Link generation may drop at idle; that is normal | REL-19, REL-5 |
| All NVLink links up | Fail | gpu-h100-07 | 4 of 126 NVLink links inactive | REL-13 |
| NVIDIA Fabric Manager running (NVSwitch systems) | Pass |  |  | LIF-9 |
| No critical XID events this boot | Fail | gpu-h100-07 | XID 48 on 0000:3a:00 (Double-bit ECC error); XID 79 on 0000:9a:00 (GPU has fallen off the bus) | REL-4, REL-9 |
| No NVSwitch SXID events this boot | Warn | gpu-h100-07 | 1 SXID events | REL-9 |
| GPUDirect RDMA path available (dma_buf or nvidia_peermem) | Fail | gpu-h100-07, gpu-a40-03 | Neither dma_buf (open module) nor nvidia_peermem: NCCL will stage through host memory | LIF-8 |
| GDRCopy installed | Warn | gpu-h100-07, gpu-a40-03 | gdrdrv module and libgdrapi not found | LIF-8 |
| ncu hardware counters available to non-root users | Fail | gpu-h100-07, gpu-a40-03 | Profiling restricted to admins | MON-1 |
| perf usable by non-root users | Warn | gpu-h100-07, gpu-a40-03 | perf restricted (ClusterMAX expects perf_event_paranoid <= 1, kptr_restrict = 0) | MON-12 |
| PCIe ACS disabled on GPU/NIC switches (bare metal) | Pass |  |  | LIF-8 |
| InfiniBand / RoCE fabric present | Pass |  |  | NET-2 |
| All RDMA ports active | Fail | gpu-h100-07, gpu-a40-03 | 1 InfiniBand port(s) not Active: mlx5_4/1 Down/Polling | REL-10, REL-21, REL-6 |
| HCAs named mlx5_* (NCCL_IB_HCA friendly) | Pass |  |  | LIF-9 |
| ConnectX firmware at or above the published minimum | Warn | gpu-h100-07 | Firmware 28.39.1002 looks older than the published minimum for its train (approximate; confirm with cmax audit) | SEC-17 |
| Tenant PKey configured on InfiniBand ports | Warn | gpu-h100-07, gpu-a40-03 | Only the default partition: tenants are not separated by PKey | SEC-9 |
| NCCL tuning left to auto-config | Warn | gpu-h100-07 | Forced in /etc/nccl.conf: NCCL_PROTO=Simple, NCCL_MIN_NCHANNELS=32 | NET-5 |
| NCCL_IB_GID_INDEX=3 set for RoCEv2 | N/A |  | InfiniBand fabric; not applicable | NET-4 |
| HPC-X / MPI available | Warn | gpu-h100-07, gpu-a40-03 | /opt/hpcx not found | NET-3 |
| NCCL installed on the host | Warn | gpu-a40-03 | libnccl not in the linker cache (fine if every job brings its own container) |  |
| CUDA toolkit (nvcc) installed | Warn | gpu-a40-03 | nvcc not found |  |
| CUDA toolkit at or above the published security minimum | Warn | gpu-h100-07 | CUDA 12.2 below 13.1 | SEC-17 |
| NVIDIA Container Toolkit patched | Fail | gpu-h100-07, gpu-a40-03 | Container Toolkit 1.16.1 below 1.19.1 (container escape CVEs, e.g. CVE-2024-0132, CVE-2025-23266) | SEC-14, SEC-15, SEC-16 |
| Docker Engine at or above the published minimum | Pass |  |  | SEC-17 |
| Pyxis + Enroot for containers under Slurm | Fail | gpu-a40-03 | Pyxis/Enroot missing | SLU-7 |
| Apptainer / Singularity available | Warn | gpu-h100-07, gpu-a40-03 | Not installed |  |
| Slurm HealthCheckProgram configured | Fail | gpu-h100-07, gpu-a40-03 | No HealthCheckProgram: failing nodes keep taking jobs | MON-16, MON-3, MON-6 |
| Slurm topology plugin configured | Warn | gpu-h100-07, gpu-a40-03 | No topology plugin: jobs ignore switch locality | NET-1, SLU-5 |
| sacct job accounting enabled | Pass |  |  | MON-15 |
| GPUs scheduled as GRES (per-GPU allocation, CUDA_VISIBLE_DEVICES set) | Warn | gpu-a40-03 | GPU GRES not configured: sub-node jobs cannot get isolated GPUs | ORC-6 |
| srun integrated with PMIx | Warn | gpu-h100-07, gpu-a40-03 | MpiDefault is not pmix | NET-3 |
| Lmod modules available | Warn | gpu-h100-07, gpu-a40-03 | Lmod not found | SLU-6 |
| High-performance parallel filesystem mounted | Warn | gpu-a40-03 | Network filesystem (NFS-class) mounted; no parallel filesystem | STO-1 |
| Shared filesystem mounted and responsive | Pass |  |  | STO-4 |
| GPU and node metrics exporters running | Fail | gpu-h100-07, gpu-a40-03 | Missing dcgm-exporter, node-exporter | MON-10, MON-14, MON-2, REL-17 |
| IPMI / BMC exporter (fans, PSU, inlet temperature) | Warn | gpu-h100-07, gpu-a40-03 | No ipmi_exporter process | REL-20 |
| DCGM host engine running (passive GPU health) | Warn | gpu-h100-07, gpu-a40-03 | nv-hostengine not running: no DCGM background health watches | MON-6, REL-18 |
| Failing nodes are drained automatically | Fail | gpu-h100-07, gpu-a40-03 | No automatic health check / drain found (HealthCheckProgram, NHC, gpud, NPD, NVSentinel, predge-ready timer) | MON-3, MON-8, REL-25 |
| DCGM diagnostic (dcgmi diag -r 3) | Fail | gpu-h100-07 | GPU Memory: Fail - GPU: 2 | MON-3, MON-7 |
| Single-node NCCL all_reduce bandwidth | Pass |  |  | NET-10, REL-11 |
| RDMA loopback bandwidth (ib_write_bw) | Pass |  |  | NET-10, REL-1 |
| GEMM throughput (bf16, torch) | Fail | gpu-h100-07 | Slow GPUs: 5 | MON-5 |
| Same NVIDIA driver on every node | Warn | cluster | 3 different driver versions | REL-14 |
| Same GPU model on every node | Warn | cluster | Mixed GPU models in one cluster | REL-14 |
| Same PKeys on every node | Fail | cluster | PKey tables differ between nodes | REL-23 |

## Nodes

| Node | GPUs | Driver / CUDA | Fabric | Health |
|---|---|---|---|---|
| gpu-h100-01 | 8x NVIDIA H100 80GB HBM3 | 580.178.04 / 13.0 | 2x Ethernet 200G up, 8x InfiniBand 400G up | healthy |
| gpu-h100-07 | 7x NVIDIA H100 80GB HBM3 | 535.183.01 / 12.2 | 1x Ethernet 200G up, 1x InfiniBand 400G DOWN, 7x InfiniBand 400G up | failing |
| gpu-a40-03 | 8x NVIDIA A40 | 550.127.05 / 12.4 | 2x InfiniBand 200G up | failing |

## Criteria

| ID | Category | Criterion | Status | Basis | Note |
|---|---|---|---|---|---|
| SEC-1 | Security | SOC 1 or SOC 2 Type II | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-2 | Security | ISO 27001 certification | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-3 | Security | GDPR, PCI, HIPAA, FedRAMP compliance | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-4 | Security | Ability to sell to secure government customers globally | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-5 | Security | Penetration testing conducted (provider, scope, coverage documented) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-6 | Security | SOC 2 and pentest specifically cover the InfiniBand/RoCEv2 fabric | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-7 | Security | Security firm with high-speed IB/Ethernet expertise | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-8 | Security | VLAN isolation between tenants for RoCE | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-9 | Security | PKeys set for InfiniBand tenants | Partial | measured | Tenant PKey configured on InfiniBand ports: Only the default partition: tenants are not separated by PKey |
| SEC-10 | Security | IB security keys management (SMKey, SAKey, CKey, VSKey) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-11 | Security | AM key configuration (if SHARP is available) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-12 | Security | Full MAD key protection and UFM hardening (8 sub-items: randomized MAD keys, GUID allow-list, service_key, enhanced SA trust, MAD limiter, DoS protection, source-LID rate limiting, SR-IOV with QP0/MAD disabled) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-13 | Security | Strong tenant isolation (not namespace or container-only) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-14 | Security | Protection against container escalation vulnerabilities | Partial | measured | NVIDIA Container Toolkit patched: Container Toolkit 1.16.1 below 1.19.1 (container escape CVEs, e.g. CVE-2024-0132, CVE-2025-23266) |
| SEC-15 | Security | NVIDIA Container Toolkit updated (CVE-2024-0132 and related) | Partial | measured | NVIDIA Container Toolkit patched: Container Toolkit 1.16.1 below 1.19.1 (container escape CVEs, e.g. CVE-2024-0132, CVE-2025-23266) |
| SEC-16 | Security | Protection against CVE-2025-23359, CVE-2025-23266 | Partial | measured | NVIDIA Container Toolkit patched: Container Toolkit 1.16.1 below 1.19.1 (container escape CVEs, e.g. CVE-2024-0132, CVE-2025-23266) |
| SEC-17 | Security | Every component at or above the published ClusterMAX minimum versions (driver, runtime, NIC/DPU firmware, host packages) | Partial | measured | NVIDIA driver at or above the published security minimum: Driver 535.183.01 is below 535.309.01 for its branch; ConnectX firmware at or above the published minimum: Firmware 28.39.1002 looks older than the published minimum for its train (approximate; confirm with cmax audit); CUDA toolkit at or above the published security minimum: CUDA 12.2 below 13.1 |
| SEC-18 | Security | Member of NVIDIA security program (embargoed patches) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-19 | Security | Automated rollout of new NVIDIA Container Toolkit on CVE discovery | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-20 | Security | Process in place for future security improvements (patch policy, customer notifications) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-1 | Lifecycle | Transparent onboarding costs and delivery timelines that are met | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-2 | Lifecycle | No punitive data egress / offboarding fees | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-3 | Lifecycle | Easy, well-documented onboarding (console or API/CLI/Terraform) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-4 | Lifecycle | Delivery date accuracy and meeting expectations | Partial | measured | GPU model matches what was sold: Node reports NVIDIA A40 but H100 was expected |
| LIF-5 | Lifecycle | Knowledge of industry experts (e.g., Sylvain) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-6 | Lifecycle | CPU head node for Slurm provisioned without explicit request | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-7 | Lifecycle | Understanding of standard ML user expectations | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-8 | Lifecycle | Out-of-the-box GPUDirect RDMA (NIC to GPU) | Partial | measured | GPUDirect RDMA path available (dma_buf or nvidia_peermem): Neither dma_buf (open module) nor nvidia_peermem: NCCL will stage through host memory; GDRCopy installed: gdrdrv module and libgdrapi not found |
| LIF-9 | Lifecycle | Out-of-the-box IB/RoCEv2 and NVIDIA driver configuration | Meets | measured | Persistence mode enabled; NVIDIA Fabric Manager running (NVSwitch systems); HCAs named mlx5_* (NCCL_IB_HCA friendly) |
| LIF-10 | Lifecycle | Performance optimization libraries (e.g., Together AI kernel collection) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-11 | Lifecycle | Audit logs cover resource actions, admin actions (roles, login success/failure) and billing events | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-12 | Lifecycle | Audit entries include actor identity (user, email, IP), action, target, timestamp, status | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-13 | Lifecycle | Audit logs queryable via API with filters (resource type, project, user, date) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-14 | Lifecycle | Minimum 90-day audit log retention with export | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-15 | Lifecycle | Audit log access restricted to admins, no extra charge | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| ORC-1 | Orchestration | Easy process for adding new cluster users | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| ORC-2 | Orchestration | RBAC and SSO implementation | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| ORC-3 | Orchestration | No SSH key copying required | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| ORC-4 | Orchestration | Storage RBAC enforcement | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| ORC-5 | Orchestration | Cluster sharing and metering with chargeback/showback | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| ORC-6 | Orchestration | CUDA_VISIBLE_DEVICES properly configured | Partial | measured | GPUs scheduled as GRES (per-GPU allocation, CUDA_VISIBLE_DEVICES set): GPU GRES not configured: sub-node jobs cannot get isolated GPUs |
| SLU-1 | Orchestration: Slurm | Automated setup process for Slurm | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SLU-2 | Orchestration: Slurm | Automated managed Slurm service | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SLU-3 | Orchestration: Slurm | Self-service capabilities (scale, settings) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SLU-4 | Orchestration: Slurm | Head node provisioning | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SLU-5 | Orchestration: Slurm | Out-of-the-box Slurm topology configuration (topology.yaml/conf) | Partial | measured | Slurm topology plugin configured: No topology plugin: jobs ignore switch locality |
| SLU-6 | Orchestration: Slurm | Slurm modules availability (Lmod) | Partial | measured | Lmod modules available: Lmod not found |
| SLU-7 | Orchestration: Slurm | Pyxis container plugin support | Partial | measured | Pyxis + Enroot for containers under Slurm: Pyxis/Enroot missing |
| K8S-1 | Orchestration: Kubernetes | Automated setup process for Kubernetes | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| K8S-2 | Orchestration: Kubernetes | Automated managed Kubernetes service | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| K8S-3 | Orchestration: Kubernetes | kubectl access or KUBECONFIG provided | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| K8S-4 | Orchestration: Kubernetes | Easy access to Kubernetes Dashboard, Lens, etc. | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| K8S-5 | Orchestration: Kubernetes | Storage accessible via PVC + hostPath + S3 | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| STO-1 | Storage | High-performance parallel filesystem out of the box (e.g., Weka, DDN, VAST) | Partial | measured | High-performance parallel filesystem mounted: Network filesystem (NFS-class) mounted; no parallel filesystem |
| STO-2 | Storage | Out-of-the-box managed S3-compatible object storage | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| STO-3 | Storage | Kubernetes PVCs / StorageClass including ReadWriteMany | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| STO-4 | Storage | Storage mounts correctly and stays mounted | Meets | measured | Shared filesystem mounted and responsive |
| STO-5 | Storage | Read and write performance measured and within expectations | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| STO-6 | Storage | Throughput and latency measurements documented | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| STO-7 | Storage | Storage scales in performance and capacity, demonstrably | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| STO-8 | Storage | Automated backups with configurable retention | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| STO-9 | Storage | Cross-region replication or backup for DR | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| STO-10 | Storage | Point-in-time recovery for managed databases | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| STO-11 | Storage | Snapshot support (CSI snapshots, filesystem snapshots) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| STO-12 | Storage | Immutable / WORM-capable storage (object lock, retention) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| STO-13 | Storage | Published durability and availability SLAs for all storage tiers | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| STO-14 | Storage | Backup encryption at rest/in transit with customer-managed keys | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| STO-15 | Storage | Centralized backup monitoring, alerting and restore validation | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| STO-16 | Storage | Checkpoint storage durability (replication factor, cross-AZ/region) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| NET-1 | Networking | Out-of-the-box Slurm topology configuration | Partial | measured | Slurm topology plugin configured: No topology plugin: jobs ignore switch locality |
| NET-2 | Networking | InfiniBand or RoCEv2 support | Meets | measured | InfiniBand / RoCE fabric present |
| NET-3 | Networking | MPI via higher-performance HPC-X mpirun | Partial | measured | HPC-X / MPI available: /opt/hpcx not found; srun integrated with PMIx: MpiDefault is not pmix |
| NET-4 | Networking | /etc/nccl.conf with NCCL_IB_GID_INDEX=3 for RoCEv2 | Meets | measured | NCCL_IB_GID_INDEX=3 set for RoCEv2 |
| NET-5 | Networking | NCCL_MIN_NCHANNELS, NCCL_PROTO, NCCL_ALGO not set (auto-config) | Partial | measured | NCCL tuning left to auto-config: Forced in /etc/nccl.conf: NCCL_PROTO=Simple, NCCL_MIN_NCHANNELS=32 |
| NET-6 | Networking | SHARP support | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| NET-7 | Networking | 4-node NCCL test within specification | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| NET-8 | Networking | PyTorch-layer network performance within spec | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| NET-9 | Networking | NCCL monitoring plugin availability | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| NET-10 | Networking | Network bandwidth and latency testing | Meets | measured | Single-node NCCL all_reduce bandwidth; RDMA loopback bandwidth (ib_write_bw) |
| REL-1 | Reliability and health checks | Network stability assessment | Meets | measured | RDMA loopback bandwidth (ib_write_bw) |
| REL-2 | Reliability and health checks | MSA SLA (99%, 99.9%, etc.) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| REL-3 | Reliability and health checks | Link flap monitoring and prevention | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| REL-4 | Reliability and health checks | GPU falling off the bus detection | Partial | measured | All GPUs visible to the driver: 7 GPUs visible to nvidia-smi, 8 expected (lspci sees more: a GPU has likely fallen off the bus); No critical XID events this boot: XID 48 on 0000:3a:00 (Double-bit ECC error); XID 79 on 0000:9a:00 (GPU has fallen off the bus) |
| REL-5 | Reliability and health checks | PCIe error monitoring | Meets | measured | GPU PCIe link at full width |
| REL-6 | Reliability and health checks | Ethernet and InfiniBand event monitoring (link flaps) | Partial | measured | All RDMA ports active: 1 InfiniBand port(s) not Active: mlx5_4/1 Down/Polling |
| REL-7 | Reliability and health checks | Thermal monitoring (GPU temperature) | Partial | measured | No hardware clock throttling: Hardware slowdown active: GPU5: HwSlowdown,HwThermalSlowdown; GPU temperatures within limits: GPU temperature at or above 87 C on GPU 5 |
| REL-8 | Reliability and health checks | GPU and CPU memory stats (ECC error rate) | Partial | measured | No uncorrectable ECC errors: Uncorrectable (volatile) ECC errors on GPU 2; No pending page retirement / row remapping: Reset pending on GPU 2 |
| REL-9 | Reliability and health checks | NVIDIA XID and SXID error detection | Partial | measured | No critical XID events this boot: XID 48 on 0000:3a:00 (Double-bit ECC error); XID 79 on 0000:9a:00 (GPU has fallen off the bus); No NVSwitch SXID events this boot: 1 SXID events |
| REL-10 | Reliability and health checks | InfiniBand health monitoring (link status, error counters, PKey consistency) | Partial | measured | All RDMA ports active: 1 InfiniBand port(s) not Active: mlx5_4/1 Down/Polling |
| REL-11 | Reliability and health checks | NCCL and Slurm topology health | Meets | measured | Single-node NCCL all_reduce bandwidth |
| REL-12 | Reliability and health checks | Kubernetes node health checks | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| REL-13 | Reliability and health checks | NVLink connectivity and error tracking | Partial | measured | All NVLink links up: 4 of 126 NVLink links inactive |
| REL-14 | Reliability and health checks | Driver and core library version consistency across nodes | Partial | measured | Same NVIDIA driver on every node: 3 different driver versions; Same GPU model on every node: Mixed GPU models in one cluster |
| REL-15 | Reliability and health checks | ECC error detection | Partial | measured | No uncorrectable ECC errors: Uncorrectable (volatile) ECC errors on GPU 2; No pending page retirement / row remapping: Reset pending on GPU 2 |
| REL-16 | Reliability and health checks | Temperature monitoring and throttling alerts | Partial | measured | No hardware clock throttling: Hardware slowdown active: GPU5: HwSlowdown,HwThermalSlowdown; GPU temperatures within limits: GPU temperature at or above 87 C on GPU 5 |
| REL-17 | Reliability and health checks | Power monitoring and utilization tracking | Partial | measured | GPU and node metrics exporters running: Missing dcgm-exporter, node-exporter |
| REL-18 | Reliability and health checks | XID/SXID detection through DCGM | Partial | measured | DCGM host engine running (passive GPU health): nv-hostengine not running: no DCGM background health watches |
| REL-19 | Reliability and health checks | PCIe bus and power state health | Meets | measured | GPU PCIe link at full width |
| REL-20 | Reliability and health checks | IPMI exporter and fan speed monitoring | Partial | measured | IPMI / BMC exporter (fans, PSU, inlet temperature): No ipmi_exporter process |
| REL-21 | Reliability and health checks | InfiniBand link status validation (ibstat) | Partial | measured | All RDMA ports active: 1 InfiniBand port(s) not Active: mlx5_4/1 Down/Polling |
| REL-22 | Reliability and health checks | Error counter monitoring (retries, dropped packets) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| REL-23 | Reliability and health checks | Partition Key (PKey) consistency across nodes | Gap | measured | Same PKeys on every node: PKey tables differ between nodes |
| REL-24 | Reliability and health checks | NCCL operation health tracking (stalled jobs) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| REL-25 | Reliability and health checks | Automated node draining and replacement | Partial | measured | Failing nodes are drained automatically: No automatic health check / drain found (HealthCheckProgram, NHC, gpud, NPD, NVSentinel, predge-ready timer) |
| MON-1 | Monitoring | ncu profiling available for all users | Partial | measured | ncu hardware counters available to non-root users: Profiling restricted to admins |
| MON-2 | Monitoring | Out-of-the-box detailed managed Grafana | Partial | measured | GPU and node metrics exporters running: Missing dcgm-exporter, node-exporter |
| MON-3 | Monitoring | Automated active and passive health checks | Partial | measured | Slurm HealthCheckProgram configured: No HealthCheckProgram: failing nodes keep taking jobs; Failing nodes are drained automatically: No automatic health check / drain found (HealthCheckProgram, NHC, gpud, NPD, NVSentinel, predge-ready timer); DCGM diagnostic (dcgmi diag -r 3): GPU Memory: Fail - GPU: 2 |
| MON-4 | Monitoring | Burn-in test documentation | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| MON-5 | Monitoring | TFLOPs estimation tracking | Partial | measured | GEMM throughput (bf16, torch): Slow GPUs: 5 |
| MON-6 | Monitoring | Comprehensive passive health check implementation | Partial | measured | Slurm HealthCheckProgram configured: No HealthCheckProgram: failing nodes keep taking jobs; DCGM host engine running (passive GPU health): nv-hostengine not running: no DCGM background health watches |
| MON-7 | Monitoring | Automated active health check implementation | Partial | measured | DCGM diagnostic (dcgmi diag -r 3): GPU Memory: Fail - GPU: 2 |
| MON-8 | Monitoring | Automatic node draining for detected issues | Partial | measured | Failing nodes are drained automatically: No automatic health check / drain found (HealthCheckProgram, NHC, gpud, NPD, NVSentinel, predge-ready timer) |
| MON-9 | Monitoring | Predictive failure detection (ML) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| MON-10 | Monitoring | Real-time system monitoring | Partial | measured | GPU and node metrics exporters running: Missing dcgm-exporter, node-exporter |
| MON-11 | Monitoring | Alerting capabilities | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| MON-12 | Monitoring | Diagnostic tools | Partial | measured | perf usable by non-root users: perf restricted (ClusterMAX expects perf_event_paranoid <= 1, kptr_restrict = 0) |
| MON-13 | Monitoring | Performance tracking | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| MON-14 | Monitoring | Resource utilization monitoring | Partial | measured | GPU and node metrics exporters running: Missing dcgm-exporter, node-exporter |
| MON-15 | Monitoring | sacct integration for job accounting | Meets | measured | sacct job accounting enabled |
| MON-16 | Monitoring | DCGM health checks plugged into Slurm HealthCheckProgram | Partial | measured | Slurm HealthCheckProgram configured: No HealthCheckProgram: failing nodes keep taking jobs |
| PRI-1 | Pricing and billing | Reasonable $/GPU/hour pricing | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| PRI-2 | Pricing and billing | Consumption options (3y, 1y, 6m, 3m, 1m) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| PRI-3 | Pricing and billing | Individual charges for storage, compute, network | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| PRI-4 | Pricing and billing | Expansion and extension of existing contracts | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| PRI-5 | Pricing and billing | Latest GPU availability and timeline | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| PRI-6 | Pricing and billing | Kernel library availability for MFU boosting | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| PRI-7 | Pricing and billing | No billing for unusable time (cluster creation, failed creates, hardware outages) [stressed in ClusterMAX 2.0] | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| PAR-1 | Partnerships | AMD or NVIDIA investment | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| PAR-2 | Partnerships | NVIDIA NCP or Lepton certification | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| PAR-3 | Partnerships | AMD Cloud Alliance status | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| PAR-4 | Partnerships | SchedMD partnership | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| PAR-5 | Partnerships | Participation in industry events | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| PAR-6 | Partnerships | Ecosystem support and integration | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| AVA-1 | Availability and support | Latest and greatest GPU models available | Gap | measured | Latest-generation GPUs on this node: not a current training GPU |
| AVA-2 | Availability and support | Current GPU models (H100, H200, A100, L40S, MI300X) | Partial | measured | GPU is a current model (H100/H200/A100/L40S/MI300X or newer): Model is not in the ClusterMAX current-model list |
| AVA-3 | Availability and support | Total GPU quantity and cluster-scale experience | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| AVA-4 | Availability and support | Availability / utilization rates | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| AVA-5 | Availability and support | Capacity planning capabilities | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| AVA-6 | Availability and support | Roadmap for future GPU acquisitions | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| AVA-7 | Availability and support | B200, B300, GB200 NVL72 availability timeline | Gap | measured | Latest-generation GPUs on this node: not a current training GPU |
| AVA-8 | Availability and support | MI355X availability planning | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| AVA-9 | Availability and support | Geographic reach and service accessibility | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| AVA-10 | Availability and support | 24x7 support with response commitments [Expectations page] | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |

Signed (ed25519) by SHA256:5cedd2f5d817ed8d0dc63b9208ccfaac at 2026-11-18T12:40:20Z. Verify with `predge-ready verify report.json`.

---
Method: the index counts Meets as 1 and Partial as 0.5 over all criteria rows. Unknown is not a failure; most Unknown rows are policy, commercial or provider-level items a node cannot show. Independent readiness estimate against the published ClusterMAX criteria. Not a SemiAnalysis rating and not affiliated with SemiAnalysis; ClusterMAX is a SemiAnalysis trademark.
