# Cluster readiness report: gpu-prod

> Independent readiness estimate against the published ClusterMAX criteria. Not a SemiAnalysis rating and not affiliated with SemiAnalysis; ClusterMAX is a SemiAnalysis trademark.

Generated 2026-11-18T12:00:00Z by predge-ready 0.1.0 (demo:healthy (recorded fixture outputs, not a live cluster)). Nodes scanned: 2.
Expected: gpu=H100, count=8, ib=8.

## Summary

- Readiness index (all 143 criteria, Unknown = 0): **37.1%**
- Index over the 54 criteria this scan could evidence: **98.1%**
- Meets 52 · Partial 2 · Gap 0 · Unknown 89
- Node health: 2 healthy, 0 warning, 0 failing

## Top fixes

1. **Latest-generation GPUs on this node** (Warn). Plan B200/B300/GB300 (or MI355X) capacity and publish the timeline. Criteria: AVA-1, AVA-7. Nodes: gpu-h100-01, gpu-h100-02.

## Categories

| Category | Rows | Meets | Partial | Gap | Unknown | Index |
|---|---|---|---|---|---|---|
| Security | 20 | 5 | 0 | 0 | 15 | 25.0% |
| Lifecycle | 15 | 3 | 0 | 0 | 12 | 20.0% |
| Orchestration | 6 | 1 | 0 | 0 | 5 | 16.7% |
| Orchestration: Slurm | 7 | 3 | 0 | 0 | 4 | 42.9% |
| Orchestration: Kubernetes | 5 | 0 | 0 | 0 | 5 | 0.0% |
| Storage | 16 | 2 | 0 | 0 | 14 | 12.5% |
| Networking | 10 | 6 | 0 | 0 | 4 | 60.0% |
| Reliability and health checks | 25 | 19 | 0 | 0 | 6 | 76.0% |
| Monitoring | 16 | 12 | 0 | 0 | 4 | 75.0% |
| Pricing and billing | 7 | 0 | 0 | 0 | 7 | 0.0% |
| Partnerships | 6 | 0 | 0 | 0 | 6 | 0.0% |
| Availability and support | 10 | 1 | 2 | 0 | 7 | 20.0% |

## Node checks

| Check | Status | Nodes affected | Detail | Criteria |
|---|---|---|---|---|
| All GPUs visible to the driver | Pass |  | 8 GPUs visible | REL-4 |
| GPU model matches what was sold | Pass |  |  | LIF-4 |
| Latest-generation GPUs on this node | Warn | gpu-h100-01, gpu-h100-02 | previous generation (Hopper / MI300); ClusterMAX expects Blackwell-class or MI355X for the top tiers | AVA-1, AVA-7 |
| GPU is a current model (H100/H200/A100/L40S/MI300X or newer) | Pass |  |  | AVA-2 |
| NVIDIA driver at or above the published security minimum | Pass |  |  | SEC-17 |
| Persistence mode enabled | Pass |  |  | LIF-9 |
| No hardware clock throttling | Pass |  |  | REL-16, REL-7 |
| GPU temperatures within limits | Pass |  |  | REL-16, REL-7 |
| No uncorrectable ECC errors | Pass |  |  | REL-15, REL-8 |
| No pending page retirement / row remapping | Pass |  |  | REL-15, REL-8 |
| GPU PCIe link at full width | Pass |  | Link generation may drop at idle; that is normal | REL-19, REL-5 |
| All NVLink links up | Pass |  |  | REL-13 |
| NVIDIA Fabric Manager running (NVSwitch systems) | Pass |  |  | LIF-9 |
| No critical XID events this boot | Pass |  | No XID events | REL-4, REL-9 |
| No NVSwitch SXID events this boot | Pass |  |  | REL-9 |
| GPUDirect RDMA path available (dma_buf or nvidia_peermem) | Pass |  | dma_buf capable (open kernel module, kernel >= 5.12) | LIF-8 |
| GDRCopy installed | Pass |  |  | LIF-8 |
| ncu hardware counters available to non-root users | Pass |  |  | MON-1 |
| perf usable by non-root users | Pass |  |  | MON-12 |
| PCIe ACS disabled on GPU/NIC switches (bare metal) | Pass |  |  | LIF-8 |
| InfiniBand / RoCE fabric present | Pass |  |  | NET-2 |
| All RDMA ports active | Pass |  |  | REL-10, REL-21 |
| HCAs named mlx5_* (NCCL_IB_HCA friendly) | Pass |  |  | LIF-9 |
| ConnectX firmware at or above the published minimum | Pass |  |  | SEC-17 |
| Tenant PKey configured on InfiniBand ports | Pass |  |  | SEC-9 |
| NCCL tuning left to auto-config | Pass |  |  | NET-5 |
| NCCL_IB_GID_INDEX=3 set for RoCEv2 | N/A |  | InfiniBand fabric; not applicable | NET-4 |
| HPC-X / MPI available | Pass |  |  | NET-3 |
| NCCL installed on the host | Pass |  |  |  |
| CUDA toolkit (nvcc) installed | Pass |  |  |  |
| CUDA toolkit at or above the published security minimum | Pass |  |  | SEC-17 |
| NVIDIA Container Toolkit patched | Pass |  |  | SEC-14, SEC-15, SEC-16 |
| Docker Engine at or above the published minimum | Pass |  |  | SEC-17 |
| Pyxis + Enroot for containers under Slurm | Pass |  |  | SLU-7 |
| Apptainer / Singularity available | Pass |  |  |  |
| Slurm HealthCheckProgram configured | Pass |  |  | MON-16, MON-3, MON-6 |
| Slurm topology plugin configured | Pass |  |  | NET-1, SLU-5 |
| sacct job accounting enabled | Pass |  |  | MON-15 |
| GPUs scheduled as GRES (per-GPU allocation, CUDA_VISIBLE_DEVICES set) | Pass |  |  | ORC-6 |
| srun integrated with PMIx | Pass |  |  | NET-3 |
| Lmod modules available | Pass |  |  | SLU-6 |
| High-performance parallel filesystem mounted | Pass |  | Parallel filesystem mounted | STO-1 |
| Shared filesystem mounted and responsive | Pass |  |  | STO-4 |
| GPU and node metrics exporters running | Pass |  |  | MON-10, MON-14, MON-2, REL-17 |
| IPMI / BMC exporter (fans, PSU, inlet temperature) | Pass |  |  | REL-20 |
| DCGM host engine running (passive GPU health) | Pass |  |  | MON-6, REL-18 |
| Failing nodes are drained automatically | Pass |  |  | MON-3, MON-8, REL-25 |
| DCGM diagnostic (dcgmi diag -r 3) | Pass |  |  | MON-3, MON-7 |
| Single-node NCCL all_reduce bandwidth | Pass |  |  | NET-10, REL-11 |
| RDMA loopback bandwidth (ib_write_bw) | Pass |  |  | NET-10, REL-1 |
| GEMM throughput (bf16, torch) | Pass |  |  | MON-5 |
| Same NVIDIA driver on every node | Pass |  |  | REL-14 |
| Same GPU model on every node | Pass |  |  | REL-14 |
| Same PKeys on every node | Pass |  |  | REL-23 |

## Nodes

| Node | GPUs | Driver / CUDA | Fabric | Health |
|---|---|---|---|---|
| gpu-h100-01 | 8x NVIDIA H100 80GB HBM3 | 580.178.04 / 13.0 | 2x Ethernet 200G up, 8x InfiniBand 400G up | healthy |
| gpu-h100-02 | 8x NVIDIA H100 80GB HBM3 | 580.178.04 / 13.0 | 2x Ethernet 200G up, 8x InfiniBand 400G up | healthy |

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
| SEC-9 | Security | PKeys set for InfiniBand tenants | Meets | measured | Tenant PKey configured on InfiniBand ports |
| SEC-10 | Security | IB security keys management (SMKey, SAKey, CKey, VSKey) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-11 | Security | AM key configuration (if SHARP is available) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-12 | Security | Full MAD key protection and UFM hardening (8 sub-items: randomized MAD keys, GUID allow-list, service_key, enhanced SA trust, MAD limiter, DoS protection, source-LID rate limiting, SR-IOV with QP0/MAD disabled) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-13 | Security | Strong tenant isolation (not namespace or container-only) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-14 | Security | Protection against container escalation vulnerabilities | Meets | measured | NVIDIA Container Toolkit patched |
| SEC-15 | Security | NVIDIA Container Toolkit updated (CVE-2024-0132 and related) | Meets | measured | NVIDIA Container Toolkit patched |
| SEC-16 | Security | Protection against CVE-2025-23359, CVE-2025-23266 | Meets | measured | NVIDIA Container Toolkit patched |
| SEC-17 | Security | Every component at or above the published ClusterMAX minimum versions (driver, runtime, NIC/DPU firmware, host packages) | Meets | measured | NVIDIA driver at or above the published security minimum; ConnectX firmware at or above the published minimum; CUDA toolkit at or above the published security minimum; Docker Engine at or above the published minimum |
| SEC-18 | Security | Member of NVIDIA security program (embargoed patches) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-19 | Security | Automated rollout of new NVIDIA Container Toolkit on CVE discovery | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SEC-20 | Security | Process in place for future security improvements (patch policy, customer notifications) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-1 | Lifecycle | Transparent onboarding costs and delivery timelines that are met | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-2 | Lifecycle | No punitive data egress / offboarding fees | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-3 | Lifecycle | Easy, well-documented onboarding (console or API/CLI/Terraform) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-4 | Lifecycle | Delivery date accuracy and meeting expectations | Meets | measured | GPU model matches what was sold |
| LIF-5 | Lifecycle | Knowledge of industry experts (e.g., Sylvain) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-6 | Lifecycle | CPU head node for Slurm provisioned without explicit request | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-7 | Lifecycle | Understanding of standard ML user expectations | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| LIF-8 | Lifecycle | Out-of-the-box GPUDirect RDMA (NIC to GPU) | Meets | measured | GPUDirect RDMA path available (dma_buf or nvidia_peermem); GDRCopy installed; PCIe ACS disabled on GPU/NIC switches (bare metal) |
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
| ORC-6 | Orchestration | CUDA_VISIBLE_DEVICES properly configured | Meets | measured | GPUs scheduled as GRES (per-GPU allocation, CUDA_VISIBLE_DEVICES set) |
| SLU-1 | Orchestration: Slurm | Automated setup process for Slurm | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SLU-2 | Orchestration: Slurm | Automated managed Slurm service | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SLU-3 | Orchestration: Slurm | Self-service capabilities (scale, settings) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SLU-4 | Orchestration: Slurm | Head node provisioning | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| SLU-5 | Orchestration: Slurm | Out-of-the-box Slurm topology configuration (topology.yaml/conf) | Meets | measured | Slurm topology plugin configured |
| SLU-6 | Orchestration: Slurm | Slurm modules availability (Lmod) | Meets | measured | Lmod modules available |
| SLU-7 | Orchestration: Slurm | Pyxis container plugin support | Meets | measured | Pyxis + Enroot for containers under Slurm |
| K8S-1 | Orchestration: Kubernetes | Automated setup process for Kubernetes | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| K8S-2 | Orchestration: Kubernetes | Automated managed Kubernetes service | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| K8S-3 | Orchestration: Kubernetes | kubectl access or KUBECONFIG provided | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| K8S-4 | Orchestration: Kubernetes | Easy access to Kubernetes Dashboard, Lens, etc. | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| K8S-5 | Orchestration: Kubernetes | Storage accessible via PVC + hostPath + S3 | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| STO-1 | Storage | High-performance parallel filesystem out of the box (e.g., Weka, DDN, VAST) | Meets | measured | High-performance parallel filesystem mounted |
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
| NET-1 | Networking | Out-of-the-box Slurm topology configuration | Meets | measured | Slurm topology plugin configured |
| NET-2 | Networking | InfiniBand or RoCEv2 support | Meets | measured | InfiniBand / RoCE fabric present |
| NET-3 | Networking | MPI via higher-performance HPC-X mpirun | Meets | measured | HPC-X / MPI available; srun integrated with PMIx |
| NET-4 | Networking | /etc/nccl.conf with NCCL_IB_GID_INDEX=3 for RoCEv2 | Meets | measured | NCCL_IB_GID_INDEX=3 set for RoCEv2 |
| NET-5 | Networking | NCCL_MIN_NCHANNELS, NCCL_PROTO, NCCL_ALGO not set (auto-config) | Meets | measured | NCCL tuning left to auto-config |
| NET-6 | Networking | SHARP support | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| NET-7 | Networking | 4-node NCCL test within specification | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| NET-8 | Networking | PyTorch-layer network performance within spec | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| NET-9 | Networking | NCCL monitoring plugin availability | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| NET-10 | Networking | Network bandwidth and latency testing | Meets | measured | Single-node NCCL all_reduce bandwidth; RDMA loopback bandwidth (ib_write_bw) |
| REL-1 | Reliability and health checks | Network stability assessment | Meets | measured | RDMA loopback bandwidth (ib_write_bw) |
| REL-2 | Reliability and health checks | MSA SLA (99%, 99.9%, etc.) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| REL-3 | Reliability and health checks | Link flap monitoring and prevention | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| REL-4 | Reliability and health checks | GPU falling off the bus detection | Meets | measured | All GPUs visible to the driver; No critical XID events this boot |
| REL-5 | Reliability and health checks | PCIe error monitoring | Meets | measured | GPU PCIe link at full width |
| REL-6 | Reliability and health checks | Ethernet and InfiniBand event monitoring (link flaps) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| REL-7 | Reliability and health checks | Thermal monitoring (GPU temperature) | Meets | measured | No hardware clock throttling; GPU temperatures within limits |
| REL-8 | Reliability and health checks | GPU and CPU memory stats (ECC error rate) | Meets | measured | No uncorrectable ECC errors; No pending page retirement / row remapping |
| REL-9 | Reliability and health checks | NVIDIA XID and SXID error detection | Meets | measured | No critical XID events this boot; No NVSwitch SXID events this boot |
| REL-10 | Reliability and health checks | InfiniBand health monitoring (link status, error counters, PKey consistency) | Meets | measured | All RDMA ports active |
| REL-11 | Reliability and health checks | NCCL and Slurm topology health | Meets | measured | Single-node NCCL all_reduce bandwidth |
| REL-12 | Reliability and health checks | Kubernetes node health checks | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| REL-13 | Reliability and health checks | NVLink connectivity and error tracking | Meets | measured | All NVLink links up |
| REL-14 | Reliability and health checks | Driver and core library version consistency across nodes | Meets | measured | Same NVIDIA driver on every node; Same GPU model on every node |
| REL-15 | Reliability and health checks | ECC error detection | Meets | measured | No uncorrectable ECC errors; No pending page retirement / row remapping |
| REL-16 | Reliability and health checks | Temperature monitoring and throttling alerts | Meets | measured | No hardware clock throttling; GPU temperatures within limits |
| REL-17 | Reliability and health checks | Power monitoring and utilization tracking | Meets | measured | GPU and node metrics exporters running |
| REL-18 | Reliability and health checks | XID/SXID detection through DCGM | Meets | measured | DCGM host engine running (passive GPU health) |
| REL-19 | Reliability and health checks | PCIe bus and power state health | Meets | measured | GPU PCIe link at full width |
| REL-20 | Reliability and health checks | IPMI exporter and fan speed monitoring | Meets | measured | IPMI / BMC exporter (fans, PSU, inlet temperature) |
| REL-21 | Reliability and health checks | InfiniBand link status validation (ibstat) | Meets | measured | All RDMA ports active |
| REL-22 | Reliability and health checks | Error counter monitoring (retries, dropped packets) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| REL-23 | Reliability and health checks | Partition Key (PKey) consistency across nodes | Meets | measured | Same PKeys on every node |
| REL-24 | Reliability and health checks | NCCL operation health tracking (stalled jobs) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| REL-25 | Reliability and health checks | Automated node draining and replacement | Meets | measured | Failing nodes are drained automatically |
| MON-1 | Monitoring | ncu profiling available for all users | Meets | measured | ncu hardware counters available to non-root users |
| MON-2 | Monitoring | Out-of-the-box detailed managed Grafana | Meets | measured | GPU and node metrics exporters running |
| MON-3 | Monitoring | Automated active and passive health checks | Meets | measured | Slurm HealthCheckProgram configured; Failing nodes are drained automatically; DCGM diagnostic (dcgmi diag -r 3) |
| MON-4 | Monitoring | Burn-in test documentation | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| MON-5 | Monitoring | TFLOPs estimation tracking | Meets | measured | GEMM throughput (bf16, torch) |
| MON-6 | Monitoring | Comprehensive passive health check implementation | Meets | measured | Slurm HealthCheckProgram configured; DCGM host engine running (passive GPU health) |
| MON-7 | Monitoring | Automated active health check implementation | Meets | measured | DCGM diagnostic (dcgmi diag -r 3) |
| MON-8 | Monitoring | Automatic node draining for detected issues | Meets | measured | Failing nodes are drained automatically |
| MON-9 | Monitoring | Predictive failure detection (ML) | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| MON-10 | Monitoring | Real-time system monitoring | Meets | measured | GPU and node metrics exporters running |
| MON-11 | Monitoring | Alerting capabilities | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| MON-12 | Monitoring | Diagnostic tools | Meets | measured | perf usable by non-root users |
| MON-13 | Monitoring | Performance tracking | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| MON-14 | Monitoring | Resource utilization monitoring | Meets | measured | GPU and node metrics exporters running |
| MON-15 | Monitoring | sacct integration for job accounting | Meets | measured | sacct job accounting enabled |
| MON-16 | Monitoring | DCGM health checks plugged into Slurm HealthCheckProgram | Meets | measured | Slurm HealthCheckProgram configured |
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
| AVA-1 | Availability and support | Latest and greatest GPU models available | Partial | measured | Latest-generation GPUs on this node: previous generation (Hopper / MI300); ClusterMAX expects Blackwell-class or MI355X for the top tiers |
| AVA-2 | Availability and support | Current GPU models (H100, H200, A100, L40S, MI300X) | Meets | measured | GPU is a current model (H100/H200/A100/L40S/MI300X or newer) |
| AVA-3 | Availability and support | Total GPU quantity and cluster-scale experience | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| AVA-4 | Availability and support | Availability / utilization rates | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| AVA-5 | Availability and support | Capacity planning capabilities | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| AVA-6 | Availability and support | Roadmap for future GPU acquisitions | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| AVA-7 | Availability and support | B200, B300, GB200 NVL72 availability timeline | Partial | measured | Latest-generation GPUs on this node: previous generation (Hopper / MI300); ClusterMAX expects Blackwell-class or MI355X for the top tiers |
| AVA-8 | Availability and support | MI355X availability planning | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| AVA-9 | Availability and support | Geographic reach and service accessibility | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |
| AVA-10 | Availability and support | 24x7 support with response commitments [Expectations page] | Unknown | not node-observable | Not observable from a node (policy, commercial or provider-level). Record it with --answers. |

Signed (ed25519) by SHA256:5cedd2f5d817ed8d0dc63b9208ccfaac at 2026-11-18T12:40:18Z. Verify with `predge-ready verify report.json`.

---
Method: the index counts Meets as 1 and Partial as 0.5 over all criteria rows. Unknown is not a failure; most Unknown rows are policy, commercial or provider-level items a node cannot show. Independent readiness estimate against the published ClusterMAX criteria. Not a SemiAnalysis rating and not affiliated with SemiAnalysis; ClusterMAX is a SemiAnalysis trademark.
