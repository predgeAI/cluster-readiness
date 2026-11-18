# Continuous GPU health checks

`predge-ready health` is a fast check of one node. It reads `nvidia-smi`, `lspci`, `nvidia-smi nvlink`, the kernel log and `ibstat`. A run takes a few seconds, so it can run every minute. Run that often, it flags a node that breaks in about two minutes.

## What it fails on

| Check | Fails when | Warns when |
|---|---|---|
| GPUs visible | `nvidia-smi` sees fewer GPUs than `lspci`, or fewer than `--expect count=N` (a GPU has fallen off the bus), or the driver does not respond | |
| XID | XID 48, 61, 62, 64, 74, 79, 92, 95, 119, 120 or 140 since boot | XID 63 or 94 (a reset is pending). Application XIDs such as 13, 31 and 43 are only reported. |
| ECC | volatile uncorrectable ECC count > 0 | |
| Row remap / page retirement | remap failure | remap or retirement pending |
| Throttling | `HwSlowdown`, `HwThermalSlowdown` or `HwPowerBrakeSlowdown` active | `SwThermalSlowdown` |
| Temperature | at or above `--temp-fail` (87 C) | at or above `--temp-warn` (80 C) |
| PCIe | link width below the maximum | |
| NVLink | any link inactive | |
| Fabric Manager | not active on an 8-GPU NVSwitch system | |
| InfiniBand | any InfiniBand port not Active, or fewer active fast ports than `--expect ib=N` | an Ethernet RDMA port is down |
| GPU model | the model does not match `--expect gpu=...` | |
| Quick NCCL (`--nccl`) | bus bandwidth below `--nccl-floor` | |

The exit codes are `0` healthy, `1` warning, `2` failing and `3` could not check (no NVIDIA tooling).

XIDs are read from the current boot only (`dmesg`, or `journalctl -k -b 0`). A reboot after the repair therefore clears them. Reading the kernel log usually needs root, which is how slurmd, systemd and cron run the check.

## Slurm: HealthCheckProgram

1. Install the tool system-wide on every node:

   ```bash
   sudo PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install git+https://github.com/predgeAI/cluster-readiness
   sudo install -m 0755 contrib/slurm/predge-ready-hc /usr/local/sbin/predge-ready-hc
   ```

2. Add the following to `slurm.conf` (also in `contrib/slurm/slurm.conf.snippet`), then run `scontrol reconfigure`:

   ```
   HealthCheckProgram=/usr/local/sbin/predge-ready-hc
   HealthCheckInterval=60
   HealthCheckNodeState=ANY,CYCLE
   ```

slurmd ignores the program's exit code, so the wrapper drains the node itself. It runs:

```
scontrol update nodename=<node> state=drain reason="predge-ready: GPU missing (7/8), XID 79, IB port down"
```

Drain rules:

- With `--resume` (the wrapper's default), a node is resumed automatically once it passes again, but only if its drain reason starts with `predge-ready:`.
- A node that an operator drained for another reason is never touched.
- To pin what a node must have, set `PREDGE_READY_EXPECT=gpu=H100,count=8,ib=8` in slurmd's environment, or edit the wrapper.

## systemd timer (Slurm or Kubernetes nodes)

```bash
sudo cp contrib/systemd/predge-ready-health.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now predge-ready-health.timer
journalctl -u predge-ready-health.service -f
```

`--drain-mode auto` picks the scheduler:

- **Slurm** when `scontrol` and `slurmd` are present. It drains with `scontrol`.
- **Kubernetes** otherwise. It runs `kubectl cordon <node>` and annotates the node with `predge.io/health=<reason>`. This needs a kubeconfig that is allowed to patch nodes, and `--node-name` or `$NODE_NAME` must match the Kubernetes node name.

## cron

```bash
sudo cp contrib/cron/predge-ready /etc/cron.d/predge-ready
```

## Kubernetes DaemonSet (outline)

Run the image privileged with `hostPID: true`, and mount the host's `/dev`, `/sys`, `/proc/driver/nvidia` and `/var/log/journal`.

1. Set `NODE_NAME` from `spec.nodeName`.
2. Use a ServiceAccount whose ClusterRole allows `get` and `patch` on `nodes`.
3. Run `predge-ready health --drain --resume --drain-mode k8s` in a loop with `sleep 60`.

If you already run NVIDIA's GPU Operator, its DCGM pod supplies `dcgmi` and `nv-hostengine`.

## Prometheus

`--textfile /var/lib/node_exporter/textfile_collector/predge_ready.prom` writes these metrics atomically for node_exporter's textfile collector:

```
predge_ready_health_status{node}                        0 healthy, 1 warning, 2 failing, 3 unknown
predge_ready_check_status{node,check}                   0 pass, 1 warn, 2 fail, 3 unknown
predge_ready_gpus_visible{node}
predge_ready_gpu_temperature_celsius{node,gpu}
predge_ready_gpu_ecc_uncorrected{node,gpu}
predge_ready_xid_events{node,xid}
predge_ready_last_run_timestamp_seconds{node}
predge_ready_run_duration_seconds{node}
```

Example alerts:

```yaml
- alert: GPUNodeFailing
  expr: predge_ready_health_status == 2
  for: 2m
- alert: GPUHealthCheckStale
  expr: time() - predge_ready_last_run_timestamp_seconds > 300
```

## Active checks on idle nodes

The passive check above is cheap. Deeper checks belong on idle or drained nodes, for example once a week from a Slurm job in a maintenance reservation:

```bash
predge-ready scan --active --no-cmax --expect gpu=H100,count=8,ib=8 --out /shared/burnin/$(hostname -s)
```

This runs the following tests when the tools are installed:

- `dcgmi diag -r 3`
- the single-node nccl-tests `all_reduce_perf` (build it from github.com/NVIDIA/nccl-tests, or pass `--nccl-tests-bin`)
- `ib_write_bw` loopback between two HCAs
- a bf16/fp16 GEMM through PyTorch

Each result is compared with a conservative floor for the GPU model. Multi-node NCCL and pairwise `ib_write_bw` across nodes are not run by this tool yet; use nccl-tests under `srun` for those.
