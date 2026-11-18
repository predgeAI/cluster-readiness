"""predge-ready command line."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__
from . import health as H
from . import render, sign
from .checks import load_minimums
from .runner import LocalRunner, Runner, SSHRunner
from .scan import DEFAULT_THRESHOLDS, assemble, build_report, demo_runners
from .score import load_criteria

DISCLAIMER = "Independent readiness estimate. Not a SemiAnalysis rating; not affiliated with SemiAnalysis. ClusterMAX is a SemiAnalysis trademark."


def parse_expect(s: Optional[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not s:
        return out
    for part in s.split(","):
        if "=" not in part:
            raise SystemExit(f"--expect: '{part}' is not key=value (keys: gpu, count, mem, ib)")
        k, v = part.split("=", 1)
        k = k.strip().lower()
        if k not in ("gpu", "count", "mem", "ib"):
            raise SystemExit(f"--expect: unknown key '{k}' (keys: gpu, count, mem, ib)")
        out[k] = v.strip()
    return out


def read_hosts(path: str) -> List[str]:
    hosts = []
    for line in Path(path).read_text().splitlines():
        line = line.split("#")[0].strip()
        if line:
            hosts.append(line.split()[0])
    return hosts


def slurm_hosts(partition: Optional[str]) -> List[str]:
    argv = ["sinfo", "-h", "-N", "-o", "%N"]
    if partition:
        argv += ["-p", partition]
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=True).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"--slurm: could not list nodes with sinfo: {exc}")
    return sorted(set(out.split()))


def write_outputs(report: Dict[str, Any], out_dir: Path, basename: str, formats: List[str]) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    if "json" in formats:
        p = out_dir / f"{basename}.json"
        p.write_text(render.to_json(report))
        paths.append(p)
    if "html" in formats:
        p = out_dir / f"{basename}.html"
        p.write_text(render.to_html(report))
        paths.append(p)
    if "md" in formats:
        p = out_dir / f"{basename}.md"
        p.write_text(render.to_markdown(report))
        paths.append(p)
    return paths


def cmd_scan(a: argparse.Namespace) -> int:
    expect = parse_expect(a.expect)
    mins = load_minimums(a.minimums)
    notes: List[str] = []
    extra: List[Dict[str, Any]] = []
    runners: List[Runner]
    mode = "live"
    if a.demo:
        runners = demo_runners(a.demo)
        mode = f"demo:{a.demo} (recorded fixture outputs, not a live cluster)"
        if not expect:
            expect = {"gpu": "H100", "count": "8", "ib": "8"}
    elif a.hosts or a.slurm is not None:
        hosts = read_hosts(a.hosts) if a.hosts else slurm_hosts(a.slurm or None)
        if not hosts:
            raise SystemExit("no hosts to scan")
        runners = [SSHRunner(h, ssh=a.ssh) for h in hosts]
        mode = f"ssh ({len(hosts)} hosts)"
    else:
        runners = [LocalRunner()]
    if not a.demo:
        from . import cmax_bridge

        if a.cmax_results:
            try:
                got, note = cmax_bridge.load_results(a.cmax_results)
            except (OSError, ValueError, RuntimeError) as exc:
                got, note = [], f"could not import cmax results: {exc}"
            extra += got
            notes.append(note)
        elif not a.no_cmax:
            if shutil.which("cmax"):
                print("Running cmax audit (SemiAnalysis clustermax CLI); use --no-cmax to skip...", file=sys.stderr)
            got, note = cmax_bridge.run_audit()
            extra += got
            notes.append(note)
    answers = None
    if a.answers:
        answers = json.loads(Path(a.answers).read_text())
        answers = {k: v for k, v in answers.items() if isinstance(v, dict)}
        notes.append(f"{len(answers)} self-attested answers loaded from {a.answers}; they only fill rows the scan could not measure.")
    thr = {"temp_warn": a.temp_warn, "temp_fail": a.temp_fail}
    opts = {"diag_level": a.diag_level, "nccl_tests_bin": a.nccl_tests_bin}
    t0 = time.time()
    report = build_report(runners, expect=expect, thresholds=thr, minimums=mins, active=a.active, active_opts=opts,
                          extra_checks=extra, notes=notes, mode=mode, name=a.name, answers=answers, parallel=a.parallel,
                          generated_at=a.generated_at)
    if a.sign:
        seed, kp, created = sign.load_or_create_key(a.key)
        if created:
            print(f"Created signing key {kp} (keep it private; publish the fingerprint)", file=sys.stderr)
        sign.sign_report(report, seed)
    formats = [f.strip() for f in a.format.split(",")]
    paths = write_outputs(report, Path(a.out), a.basename, formats)
    s = report["score"]
    h = report["health"]
    print(f"predge-ready {__version__} · {report['cluster']['name']} · {len(report['nodes'])} node(s) · {time.time() - t0:.1f}s")
    print(f"Readiness index: {s['index']}% of {s['total']} criteria (Meets {s['counts']['Meets']}, Partial {s['counts']['Partial']}, "
          f"Gap {s['counts']['Gap']}, Unknown {s['counts']['Unknown']})"
          + (f"; {s['assessed_index']}% over the {s['assessed']} rows this scan evidenced" if s.get("assessed_index") is not None else ""))
    print(f"Node health: {h['healthy']} healthy, {h['warning']} warning, {h['failing']} failing, {h['unknown']} unknown")
    for n in report["notes"]:
        if n.startswith("No NVIDIA GPUs"):
            print("Note: " + n)
    for i, f in enumerate(report["top_fixes"][:5], 1):
        print(f"  {i}. [{f['status']}] {f['title']}: {f['fix']}")
    for p in paths:
        print(f"wrote {p}")
    print(DISCLAIMER)
    if a.fail_under is not None and s["index"] < a.fail_under:
        return 2
    return 0


def cmd_health(a: argparse.Namespace) -> int:
    t0 = time.time()
    expect = parse_expect(a.expect)
    mins = load_minimums(a.minimums)
    thr = {"temp_warn": a.temp_warn, "temp_fail": a.temp_fail}
    r: Runner = demo_runners(a.demo)[0 if a.demo == "healthy" else 1] if a.demo else LocalRunner()
    if a.demo and not expect:
        expect = {"gpu": "H100", "count": "8"}
    try:
        state, checks, facts = H.evaluate(r, expect, thr, mins, nccl=a.nccl, nccl_floor=a.nccl_floor, nccl_bin=a.nccl_tests_bin)
    except Exception as exc:  # never crash a HealthCheckProgram
        print(f"predge-ready health: internal error: {exc}", file=sys.stderr)
        return 3
    node = a.node_name or os.environ.get("SLURMD_NODENAME") or os.environ.get("NODE_NAME") or facts.get("host") or socket.gethostname().split(".")[0]
    log: List[str] = []
    if a.drain or a.resume:
        mode = a.drain_mode if a.drain_mode != "auto" else H.detect_mode(lambda t: shutil.which(t) is not None)
        if a.demo:
            mode = "slurm" if a.drain_mode == "auto" else a.drain_mode
        log = H.act(state, checks, mode=mode or "", node=node, drain=a.drain, resume=a.resume, dry_run=a.dry_run or bool(a.demo))
    if a.textfile:
        try:
            H.write_textfile(a.textfile, H.prometheus(node, state, checks, facts, time.time() - t0))
        except OSError as exc:
            log.append(f"could not write {a.textfile}: {exc}")
    if a.json:
        print(json.dumps({"node": node, "state": state, "exit_code": H.EXIT[state], "checks": checks, "actions": log}, indent=2))
    elif not a.quiet or state != "healthy":
        print(f"{node}: {state.upper()} ({time.time() - t0:.1f}s)")
        for c in checks:
            if c["status"] in ("fail", "warn") or (a.verbose and c["status"] != "na"):
                print(f"  [{c['status']}] {c['title']}: {c['reason'] or 'ok'}")
        for line in log:
            print(f"  {line}")
    return H.EXIT[state]


def cmd_verify(a: argparse.Namespace) -> int:
    try:
        report = json.loads(Path(a.report).read_text())
    except (OSError, ValueError) as exc:
        print(f"cannot read {a.report}: {exc}", file=sys.stderr)
        return 2
    ok, msg = sign.verify_report(report, a.pubkey)
    print(("OK: " if ok else "FAILED: ") + msg)
    return 0 if ok else 1


def cmd_keygen(a: argparse.Namespace) -> int:
    seed, p, created = sign.load_or_create_key(a.key)
    pub = sign.public_key(seed)
    print(f"{'created' if created else 'existing'} key: {p}")
    print(f"public key:  {pub.hex()}")
    print(f"fingerprint: {sign.fingerprint(pub)}")
    return 0


def cmd_criteria(a: argparse.Namespace) -> int:
    for c in load_criteria():
        print(f"{c['id']:7} {c['category']:32} {c['criterion']}")
    return 0


def cmd_answers_template(a: argparse.Namespace) -> int:
    tpl = {c["id"]: {"status": "Unknown", "evidence": "", "criterion": c["criterion"]} for c in load_criteria()}
    print(json.dumps(tpl, indent=1))
    return 0


def cmd_merge(a: argparse.Namespace) -> int:
    nodes: List[Dict[str, Any]] = []
    extra: List[Dict[str, Any]] = []
    expect: Dict[str, str] = {}
    active = False
    for p in a.reports:
        r = json.loads(Path(p).read_text())
        nodes += r["nodes"]
        extra += r.get("extra_checks") or []
        expect = expect or r.get("expect") or {}
        active = active or r.get("active_tests", False)
    report = assemble(nodes, expect=expect, extra_checks=extra, notes=[f"merged from {len(a.reports)} reports"], mode="merged", name=a.name, active=active)
    if a.sign:
        seed, _, _ = sign.load_or_create_key(a.key)
        sign.sign_report(report, seed)
    for p in write_outputs(report, Path(a.out), a.basename, [f.strip() for f in a.format.split(",")]):
        print(f"wrote {p}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="predge-ready", description="GPU cluster readiness against published ClusterMAX criteria, plus node health checks. " + DISCLAIMER)
    ap.add_argument("--version", action="version", version=f"predge-ready {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--expect", help="what the node should have, e.g. gpu=H100,count=8,mem=80,ib=8")
        p.add_argument("--temp-warn", type=float, default=DEFAULT_THRESHOLDS["temp_warn"], help="GPU temperature warning, C (default 80)")
        p.add_argument("--temp-fail", type=float, default=DEFAULT_THRESHOLDS["temp_fail"], help="GPU temperature failure, C (default 87)")
        p.add_argument("--minimums", help="minimum-versions JSON to use instead of the bundled snapshot")
        p.add_argument("--nccl-tests-bin", default="all_reduce_perf", help="path to nccl-tests all_reduce_perf")

    s = sub.add_parser("scan", help="scan this node (or many) and write a scored readiness report")
    common(s)
    s.add_argument("--active", action="store_true", help="also run active tests if the tools exist: dcgmi diag, nccl-tests, ib_write_bw, torch GEMM (loads the GPUs; use idle nodes)")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--hosts", help="file with one host per line; scanned over SSH (BatchMode, your SSH config)")
    g.add_argument("--slurm", nargs="?", const="", metavar="PARTITION", help="scan every node sinfo lists (optionally one partition) over SSH")
    g.add_argument("--demo", choices=["healthy", "broken"], help="render a report from recorded fixture outputs")
    s.add_argument("--ssh", default="ssh", help="ssh binary (default ssh)")
    s.add_argument("--parallel", type=int, default=16, help="hosts scanned in parallel (default 16)")
    s.add_argument("--out", default="predge-ready-report", help="output directory (default ./predge-ready-report)")
    s.add_argument("--basename", default="report", help="output file name without extension (default report)")
    s.add_argument("--format", default="json,html,md", help="comma list of json,html,md")
    s.add_argument("--name", help="cluster name shown in the report")
    s.add_argument("--sign", action="store_true", help="sign the JSON report with a local Ed25519 key")
    s.add_argument("--key", help=f"signing key path (default {sign.default_key_path()})")
    s.add_argument("--answers", help="JSON with self-attested statuses for rows a node cannot show (see answers-template)")
    s.add_argument("--no-cmax", action="store_true", help="do not run SemiAnalysis' cmax audit even if it is installed")
    s.add_argument("--cmax-results", help="merge an existing cmax audit directory or audit.values.json instead of running cmax")
    s.add_argument("--diag-level", type=int, default=3, choices=[1, 2, 3, 4], help="dcgmi diag level for --active (default 3)")
    s.add_argument("--fail-under", type=float, help="exit 2 if the readiness index is below this percentage")
    s.add_argument("--generated-at", help=argparse.SUPPRESS)
    s.set_defaults(func=cmd_scan)

    h = sub.add_parser("health", help="fast node health check with exit codes; optional drain/cordon and Prometheus metrics")
    common(h)
    h.add_argument("--drain", action="store_true", help="drain (Slurm) or cordon (Kubernetes) this node when it is failing")
    h.add_argument("--resume", action="store_true", help="resume/uncordon the node when healthy again, only if predge-ready drained it")
    h.add_argument("--drain-mode", choices=["auto", "slurm", "k8s"], default="auto")
    h.add_argument("--node-name", help="scheduler node name (default $SLURMD_NODENAME, $NODE_NAME or short hostname)")
    h.add_argument("--dry-run", action="store_true", help="print drain commands instead of running them")
    h.add_argument("--nccl", action="store_true", help="add a quick single-node NCCL all_reduce (about 10 s; only on idle nodes)")
    h.add_argument("--nccl-floor", type=float, help="minimum busbw in GB/s for --nccl")
    h.add_argument("--textfile", help="write Prometheus metrics here (node_exporter textfile collector), e.g. /var/lib/node_exporter/textfile_collector/predge_ready.prom")
    h.add_argument("--json", action="store_true", help="print JSON")
    h.add_argument("--quiet", "-q", action="store_true", help="print nothing when healthy")
    h.add_argument("--verbose", "-v", action="store_true", help="list passing checks too")
    h.add_argument("--demo", choices=["healthy", "broken"], help="run against recorded fixture outputs (drain is always dry-run)")
    h.set_defaults(func=cmd_health)

    v = sub.add_parser("verify", help="verify the Ed25519 signature of a report JSON")
    v.add_argument("report")
    v.add_argument("--pubkey", help="require this public key (hex) or fingerprint (SHA256:...)")
    v.set_defaults(func=cmd_verify)

    k = sub.add_parser("keygen", help="create (or show) the local signing key")
    k.add_argument("--key")
    k.set_defaults(func=cmd_keygen)

    c = sub.add_parser("criteria", help="list the 143 criteria rows used for scoring")
    c.set_defaults(func=cmd_criteria)
    t = sub.add_parser("answers-template", help="print a JSON template for self-attested answers")
    t.set_defaults(func=cmd_answers_template)

    m = sub.add_parser("merge", help="merge per-node report JSONs (e.g. from srun) into one cluster report")
    m.add_argument("reports", nargs="+")
    m.add_argument("--out", default="predge-ready-report")
    m.add_argument("--basename", default="cluster")
    m.add_argument("--format", default="json,html,md")
    m.add_argument("--name")
    m.add_argument("--sign", action="store_true")
    m.add_argument("--key")
    m.set_defaults(func=cmd_merge)
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
