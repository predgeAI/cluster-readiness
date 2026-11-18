"""Tests for predge-ready. Run with: python -m unittest discover -s tests (or pytest)."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from predge_ready import cli, health, parsers as P, render, sign  # noqa: E402
from predge_ready.checks import load_minimums, node_checks  # noqa: E402
from predge_ready.collect import collect  # noqa: E402
from predge_ready.runner import FixtureRunner  # noqa: E402
from predge_ready.scan import DEFAULT_THRESHOLDS, build_report, demo_runners, fixture_root  # noqa: E402
from predge_ready.score import load_criteria  # noqa: E402

MINS = load_minimums()
EXPECT = {"gpu": "H100", "count": "8", "ib": "8"}


def checks_for(node: str, active: bool = True, expect=None):
    r = FixtureRunner(fixture_root() / node)
    facts = collect(r, active=active)
    return {c["id"]: c for c in node_checks(facts, expect if expect is not None else EXPECT, DEFAULT_THRESHOLDS, MINS)}, facts


class TestParsers(unittest.TestCase):
    def test_throttle_bits(self):
        g = P.normalize_gpu({"index": "0", "clocks_event_reasons.active": "0x0000000000000048"})
        self.assertEqual(sorted(g["throttle_reasons"]), ["HwSlowdown", "HwThermalSlowdown"])

    def test_xid(self):
        xids, sxids = P.parse_xids("[1.0] NVRM: Xid (PCI:0000:9a:00): 79, pid='<unknown>', name=<unknown>, GPU has fallen off the bus.\n"
                                   "[2.0] NVRM: Xid (PCI:0000:17:00): 13, pid=1, name=python, Graphics Exception\n"
                                   "[3.0] nvidia-nvswitch2: SXid (PCI:0000:07:00.0): 12028, Non-fatal")
        self.assertEqual([(x["xid"], x["severity"]) for x in xids], [(79, "fail"), (13, "info")])
        self.assertEqual(sxids[0]["sxid"], 12028)

    def test_ibstat(self):
        ports = P.parse_ibstat((fixture_root() / "gpu-h100-07" / "commands" / "ibstat.txt").read_text())
        self.assertEqual(len(ports), 9)
        self.assertEqual([p["ca"] for p in ports if p["state"] == "Down"], ["mlx5_4"])
        self.assertEqual(ports[0]["rate"], 400)

    def test_lspci_count_ignores_nvswitch(self):
        self.assertEqual(P.count_lspci_gpus((fixture_root() / "gpu-h100-01" / "commands" / "lspci_nvidia.txt").read_text()), 8)

    def test_versions(self):
        self.assertTrue(P.version_ge("580.178.04", "580.178.04"))
        self.assertFalse(P.version_ge("535.183.01", "535.309.01"))
        self.assertTrue(P.version_ge("1.19.1", "1.19"))

    def test_bench_parsers(self):
        self.assertAlmostEqual(P.parse_nccl_tests("# Avg bus bandwidth    : 478.31\n"), 478.31)
        self.assertAlmostEqual(P.parse_ib_write_bw((fixture_root() / "gpu-h100-01" / "commands" / "ib_write_bw.txt").read_text()), 392.51)
        d = P.parse_dcgm_diag((fixture_root() / "gpu-h100-07" / "commands" / "dcgm_diag.txt").read_text())
        self.assertEqual(len(d["failed"]), 1)
        self.assertEqual(len(d["warnings"]), 1)


class TestHealthyNode(unittest.TestCase):
    def test_all_health_checks_pass(self):
        c, _ = checks_for("gpu-h100-01")
        for cid in ("gpu.count", "gpu.model", "gpu.throttle", "gpu.temperature", "gpu.ecc", "gpu.xid", "gpu.nvlink",
                    "ib.ports_up", "gpu.gpudirect_rdma", "containers.toolkit", "gpu.driver_version", "slurm.healthcheck",
                    "health.auto_drain", "active.dcgm_diag", "active.nccl", "active.ib_write_bw", "active.gemm"):
            self.assertEqual(c[cid]["status"], "pass", f"{cid}: {c[cid]}")
        self.assertEqual(c["nccl.roce_gid"]["status"], "na")

    def test_health_command_exit_0(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["health", "--demo", "healthy", "-q"]), 0)


class TestBrokenNodes(unittest.TestCase):
    def setUp(self):
        self.c, self.facts = checks_for("gpu-h100-07")

    def test_missing_gpu_and_xid79(self):
        self.assertEqual(self.c["gpu.count"]["status"], "fail")
        self.assertIn("fallen off the bus", self.c["gpu.count"]["reason"])
        self.assertEqual(self.c["gpu.xid"]["status"], "fail")
        self.assertIn(79, self.c["gpu.xid"]["observed"]["xid_codes"])

    def test_throttling_and_temperature(self):
        self.assertEqual(self.c["gpu.throttle"]["status"], "fail")
        self.assertIn("HwThermalSlowdown", self.c["gpu.throttle"]["reason"])
        self.assertEqual(self.c["gpu.temperature"]["status"], "fail")

    def test_ecc(self):
        self.assertEqual(self.c["gpu.ecc"]["status"], "fail")
        self.assertEqual(self.c["gpu.row_remap"]["status"], "warn")

    def test_old_driver_field_fallback(self):
        gpus = self.facts["gpu"]["gpus"]
        self.assertEqual(len(gpus), 7)
        self.assertIsNotNone(gpus[0]["throttle_mask"])

    def test_ib_down(self):
        self.assertEqual(self.c["ib.ports_up"]["status"], "fail")
        self.assertIn("mlx5_4", self.c["ib.ports_up"]["reason"])

    def test_security_versions(self):
        self.assertEqual(self.c["gpu.driver_version"]["status"], "fail")
        self.assertEqual(self.c["containers.toolkit"]["status"], "fail")

    def test_active_failures(self):
        self.assertEqual(self.c["active.dcgm_diag"]["status"], "fail")
        self.assertEqual(self.c["active.gemm"]["status"], "fail")

    def test_a40_where_h100_expected(self):
        c, _ = checks_for("gpu-a40-03")
        self.assertEqual(c["gpu.model"]["status"], "fail")
        self.assertIn("A40", c["gpu.model"]["reason"])
        self.assertEqual(c["ib.ports_up"]["status"], "fail")  # 2 rails where 8 expected
        self.assertEqual(c["gpu.xid"]["status"], "pass")  # XID 13 is application-class
        self.assertEqual(c["gpu.nvlink"]["status"], "na")
        c2, _ = checks_for("gpu-a40-03", expect={"gpu": "A100"})
        self.assertEqual(c2["gpu.model"]["status"], "fail")

    def test_no_expectation_is_unknown(self):
        c, _ = checks_for("gpu-a40-03", expect={})
        self.assertEqual(c["gpu.model"]["status"], "unknown")

    def test_health_exit_2_and_drain_command(self):
        state, checks, facts = health.evaluate(FixtureRunner(fixture_root() / "gpu-h100-07"), {"gpu": "H100", "count": "8"}, DEFAULT_THRESHOLDS, MINS)
        self.assertEqual(state, "failing")
        self.assertEqual(health.EXIT[state], 2)
        calls = []

        def fake(argv):
            calls.append(argv)
            if argv[:3] == ["scontrol", "show", "node"]:
                return 0, "NodeName=gpu-h100-07 State=MIXED ThreadsPerCore=2"
            return 0, ""

        log = health.act(state, checks, mode="slurm", node="gpu-h100-07", drain=True, resume=False, dry_run=False, run=fake)
        upd = [c for c in calls if c[:2] == ["scontrol", "update"]]
        self.assertEqual(len(upd), 1)
        self.assertIn("state=drain", upd[0])
        reason = [a for a in upd[0] if a.startswith("reason=")][0]
        self.assertIn("XID", reason)
        self.assertTrue(reason.startswith("reason=predge-ready:"))
        self.assertTrue(any(line.startswith("ran:") for line in log))

    def test_already_drained_is_left_alone(self):
        state, checks, _ = health.evaluate(FixtureRunner(fixture_root() / "gpu-h100-07"), {}, DEFAULT_THRESHOLDS, MINS)
        calls = []

        def fake(argv):
            calls.append(argv)
            return 0, "State=IDLE+DRAIN Reason=hardware ticket 42 [root@2026-11-18]"

        health.act(state, checks, mode="slurm", node="n", drain=True, resume=False, dry_run=False, run=fake)
        self.assertFalse([c for c in calls if c[:2] == ["scontrol", "update"]])

    def test_resume_only_own_drains(self):
        state, checks, _ = health.evaluate(FixtureRunner(fixture_root() / "gpu-h100-01"), {}, DEFAULT_THRESHOLDS, MINS)
        self.assertEqual(state, "healthy")
        for reason, expect_resume in (("predge-ready: XID 79", True), ("hardware ticket 42", False)):
            calls = []

            def fake(argv, reason=reason):
                calls.append(argv)
                return 0, f"State=IDLE+DRAIN Reason={reason} [root@2026-11-18]"

            health.act(state, checks, mode="slurm", node="n", drain=True, resume=True, dry_run=False, run=fake)
            self.assertEqual(any("state=resume" in c for c in calls), expect_resume)

    def test_k8s_cordon(self):
        state, checks, _ = health.evaluate(FixtureRunner(fixture_root() / "gpu-h100-07"), {}, DEFAULT_THRESHOLDS, MINS)
        log = health.act(state, checks, mode="k8s", node="n1", drain=True, resume=False, dry_run=True)
        self.assertIn("would run: kubectl cordon n1", log)

    def test_prometheus_textfile(self):
        state, checks, facts = health.evaluate(FixtureRunner(fixture_root() / "gpu-h100-07"), {}, DEFAULT_THRESHOLDS, MINS)
        text = health.prometheus("n1", state, checks, facts, 0.2)
        self.assertIn('predge_ready_health_status{node="n1"} 2', text)
        self.assertIn('predge_ready_xid_events{node="n1",xid="79"} 1', text)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.prom")
            health.write_textfile(p, text)
            self.assertEqual(Path(p).read_text(), text)


class TestMissingTools(unittest.TestCase):
    def test_empty_node_degrades_to_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "tools.txt").write_text("")
            r = FixtureRunner(Path(d))
            facts = collect(r, active=True)
            cs = {c["id"]: c for c in node_checks(facts, {}, DEFAULT_THRESHOLDS, MINS)}
            self.assertEqual(cs["gpu.count"]["status"], "unknown")
            self.assertIn("nvidia-smi not installed", cs["gpu.count"]["reason"])
            self.assertEqual(cs["ib.ports_up"]["status"], "unknown")
            state, _, _ = health.evaluate(r, {}, DEFAULT_THRESHOLDS, MINS)
            self.assertEqual(state, "unknown")


class TestScoring(unittest.TestCase):
    def test_criteria_catalogue(self):
        rows = load_criteria()
        self.assertEqual(len(rows), 143)
        self.assertEqual(len({r["id"] for r in rows}), 143)

    def test_mapped_criteria_exist(self):
        ids = {r["id"] for r in load_criteria()}
        for node in ("gpu-h100-01", "gpu-h100-07", "gpu-a40-03"):
            c, _ = checks_for(node)
            for chk in c.values():
                for cid in chk["criteria"]:
                    self.assertIn(cid, ids, f"{chk['id']} maps to unknown criterion {cid}")

    def test_healthy_scores_higher(self):
        good = build_report(demo_runners("healthy"), expect=EXPECT, minimums=MINS, active=True)
        bad = build_report(demo_runners("broken"), expect=EXPECT, minimums=MINS, active=True)
        self.assertGreater(good["score"]["index"], bad["score"]["index"])
        self.assertEqual(good["health"]["failing"], 0)
        self.assertEqual(bad["health"]["failing"], 2)
        self.assertEqual(sum(good["score"]["counts"].values()), 143)
        self.assertEqual(bad["top_fixes"][0]["check"], "nodes.failing")
        self.assertIn("SemiAnalysis", render.to_html(bad))

    def test_answers_fill_unknown_only(self):
        rep = build_report(demo_runners("healthy"), expect=EXPECT, minimums=MINS,
                           answers={"SEC-1": {"status": "Meets", "evidence": "SOC 2 Type II"}, "REL-4": {"status": "Gap"}})
        rows = {r["id"]: r for r in rep["score"]["rows"]}
        self.assertEqual((rows["SEC-1"]["status"], rows["SEC-1"]["basis"]), ("Meets", "self-attested"))
        self.assertEqual(rows["REL-4"]["status"], "Meets")  # measured wins over self-attested


class TestSigning(unittest.TestCase):
    def test_rfc8032_vector_1(self):
        sk = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
        pk = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
        sig = bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
        self.assertEqual(sign.pure_public_key(sk), pk)
        self.assertEqual(sign.pure_sign(sk, b""), sig)
        self.assertTrue(sign.pure_verify(pk, b"", sig))
        self.assertFalse(sign.pure_verify(pk, b"x", sig))

    def test_report_roundtrip_and_tamper(self):
        seed = bytes(range(32))
        rep = build_report(demo_runners("healthy"), expect=EXPECT, minimums=MINS)
        rep = json.loads(json.dumps(sign.sign_report(rep, seed)))
        ok, _ = sign.verify_report(rep)
        self.assertTrue(ok)
        ok, _ = sign.verify_report(rep, rep["signature"]["fingerprint"])
        self.assertTrue(ok)
        ok, msg = sign.verify_report(rep, "SHA256:deadbeef")
        self.assertFalse(ok)
        rep["score"]["index"] = 99.9
        ok, msg = sign.verify_report(rep)
        self.assertFalse(ok)
        self.assertIn("modified", msg)

    def test_cli_scan_sign_verify(self):
        with tempfile.TemporaryDirectory() as d:
            with redirect_stdout(io.StringIO()):
                rc = cli.main(["scan", "--demo", "broken", "--active", "--sign", "--key", os.path.join(d, "k"), "--out", d])
                self.assertEqual(rc, 0)
                self.assertEqual(cli.main(["verify", os.path.join(d, "report.json")]), 0)
            self.assertEqual(oct(os.stat(os.path.join(d, "k")).st_mode & 0o777), "0o600")
            for ext in ("json", "html", "md"):
                self.assertTrue(Path(d, f"report.{ext}").stat().st_size > 1000)
            html = Path(d, "report.html").read_text()
            self.assertNotIn("<script", html)
            self.assertNotIn("http://", html.split("<body>")[0])


if __name__ == "__main__":
    unittest.main()
