"""Command runners: local host, a remote host over SSH, or recorded fixtures.

Every probe goes through a runner so the same collectors work on a live node,
on remote nodes (``--hosts`` / ``--slurm``) and on recorded outputs (tests and
``--demo``). A runner never raises for a missing tool or an unreadable file; it
reports that as ``missing=True`` or ``None`` so checks can degrade to Unknown.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Result:
    rc: int = 0
    out: str = ""
    err: str = ""
    missing: bool = False
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return not self.missing and not self.timed_out and self.rc == 0


_ENV = dict(os.environ, LC_ALL="C", LANG="C")


class Runner:
    host = "localhost"

    def which(self, tool: str) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    def run(self, key: str, argv: List[str], timeout: float = 20.0) -> Result:  # pragma: no cover
        raise NotImplementedError

    def read(self, path: str) -> Optional[str]:  # pragma: no cover
        raise NotImplementedError

    def listdir(self, path: str) -> Optional[List[str]]:  # pragma: no cover
        raise NotImplementedError

    def is_root(self) -> bool:  # pragma: no cover
        raise NotImplementedError


class LocalRunner(Runner):
    def __init__(self) -> None:
        import socket

        self.host = socket.gethostname().split(".")[0]

    def which(self, tool: str) -> bool:
        if tool.startswith("/"):
            return os.path.exists(tool)
        return shutil.which(tool) is not None

    def run(self, key: str, argv: List[str], timeout: float = 20.0) -> Result:
        if not self.which(argv[0]):
            return Result(rc=127, missing=True, err=f"{argv[0]} not found")
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout,
                env=_ENV,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            return Result(rc=124, timed_out=True, err=f"timed out after {timeout:.0f}s")
        except OSError as exc:
            return Result(rc=126, missing=True, err=str(exc))
        return Result(rc=proc.returncode, out=proc.stdout, err=proc.stderr)

    def read(self, path: str) -> Optional[str]:
        try:
            with open(path, "r", errors="replace") as fh:
                return fh.read()
        except OSError:
            return None

    def listdir(self, path: str) -> Optional[List[str]]:
        try:
            return sorted(os.listdir(path))
        except OSError:
            return None

    def is_root(self) -> bool:
        return hasattr(os, "geteuid") and os.geteuid() == 0


class SSHRunner(Runner):
    """Runs probes on a remote host with the operator's own SSH config.

    Uses BatchMode so it never prompts for a password. Nothing is installed on
    the remote host; each probe is a single read-only command.
    """

    def __init__(self, host: str, ssh: str = "ssh", connect_timeout: int = 8) -> None:
        self.host = host
        self._ssh = [ssh, "-o", "BatchMode=yes", "-o", f"ConnectTimeout={connect_timeout}", host, "--"]
        self._which: Dict[str, bool] = {}
        self._root: Optional[bool] = None

    def _remote(self, command: str, timeout: float) -> Result:
        try:
            proc = subprocess.run(
                self._ssh + [command],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout + 10,
                env=_ENV,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            return Result(rc=124, timed_out=True, err="ssh timed out")
        except OSError as exc:
            return Result(rc=126, missing=True, err=str(exc))
        if proc.returncode == 255:
            return Result(rc=255, missing=True, err=proc.stderr.strip() or "ssh failed")
        return Result(rc=proc.returncode, out=proc.stdout, err=proc.stderr)

    def reachable(self) -> Result:
        return self._remote("true", 10)

    def which(self, tool: str) -> bool:
        if tool not in self._which:
            test = f"test -e {shlex.quote(tool)}" if tool.startswith("/") else f"command -v {shlex.quote(tool)} >/dev/null"
            self._which[tool] = self._remote(test, 10).rc == 0
        return self._which[tool]

    def run(self, key: str, argv: List[str], timeout: float = 20.0) -> Result:
        if not self.which(argv[0]):
            return Result(rc=127, missing=True, err=f"{argv[0]} not found on {self.host}")
        cmd = "LC_ALL=C timeout {} {}".format(int(timeout), " ".join(shlex.quote(a) for a in argv))
        return self._remote(cmd, timeout)

    def read(self, path: str) -> Optional[str]:
        res = self._remote(f"cat {shlex.quote(path)}", 10)
        return res.out if res.rc == 0 else None

    def listdir(self, path: str) -> Optional[List[str]]:
        res = self._remote(f"ls -1 {shlex.quote(path)}", 10)
        return sorted(res.out.split()) if res.rc == 0 else None

    def is_root(self) -> bool:
        if self._root is None:
            res = self._remote("id -u", 10)
            self._root = res.out.strip() == "0"
        return self._root


class FixtureRunner(Runner):
    """Replays recorded command output from a fixture directory.

    Layout::

        <dir>/tools.txt            tools present on the node, one per line
        <dir>/root                 present if the recording was made as root
        <dir>/commands/<key>.txt   stdout of the probe with that key
        <dir>/commands/<key>.rc    optional exit code (default 0)
        <dir>/files/<abs path>     file contents, e.g. files/proc/modules
    """

    def __init__(self, path: Path) -> None:
        self.dir = Path(path)
        tools = self.dir / "tools.txt"
        self._tools = set(tools.read_text().split()) if tools.exists() else set()
        hostname = self.dir / "commands" / "hostname.txt"
        self.host = hostname.read_text().strip() if hostname.exists() else self.dir.name

    def which(self, tool: str) -> bool:
        if tool.startswith("/"):
            return (self.dir / "files" / tool.lstrip("/")).exists() or tool in self._tools
        return tool in self._tools

    def run(self, key: str, argv: List[str], timeout: float = 20.0) -> Result:
        if not self.which(argv[0]):
            return Result(rc=127, missing=True, err=f"{argv[0]} not found")
        out = self.dir / "commands" / f"{key}.txt"
        if not out.exists():
            return Result(rc=127, missing=True, err=f"no recording for {key}")
        rc_file = self.dir / "commands" / f"{key}.rc"
        rc = int(rc_file.read_text().strip()) if rc_file.exists() else 0
        text = out.read_text()
        return Result(rc=rc, out=text if rc == 0 else "", err=text if rc != 0 else "")

    def read(self, path: str) -> Optional[str]:
        p = self.dir / "files" / path.lstrip("/")
        return p.read_text() if p.is_file() else None

    def listdir(self, path: str) -> Optional[List[str]]:
        p = self.dir / "files" / path.lstrip("/")
        return sorted(x.name for x in p.iterdir()) if p.is_dir() else None

    def is_root(self) -> bool:
        return (self.dir / "root").exists()
