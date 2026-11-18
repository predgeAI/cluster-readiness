"""Ed25519 signing of report JSON.

Uses the ``cryptography`` package when it is installed, otherwise a small
pure-Python Ed25519 (RFC 8032) so the tool stays stdlib-only. Signing a report
is rare and slow-path friendly; the pure version takes well under a second.

The signature covers the canonical JSON of the report without its
``signature`` field (sorted keys, compact separators, UTF-8).
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# ---- pure-Python Ed25519 (RFC 8032, section 5.1) -------------------------------

_p = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_d = (-121665 * pow(121666, _p - 2, _p)) % _p
_I = pow(2, (_p - 1) // 4, _p)


def _inv(x: int) -> int:
    return pow(x, _p - 2, _p)


def _recover_x(y: int, sign: int) -> Optional[int]:
    if y >= _p:
        return None
    x2 = (y * y - 1) * _inv(_d * y * y + 1) % _p
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_p + 3) // 8, _p)
    if (x * x - x2) % _p != 0:
        x = x * _I % _p
    if (x * x - x2) % _p != 0:
        return None
    if (x & 1) != sign:
        x = _p - x
    return x


_gy = 4 * _inv(5) % _p
_gx = _recover_x(_gy, 0)
_G = (_gx, _gy, 1, _gx * _gy % _p)


def _add(P: Tuple[int, int, int, int], Q: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % _p
    B = (P[1] + P[0]) * (Q[1] + Q[0]) % _p
    C = 2 * P[3] * Q[3] * _d % _p
    D = 2 * P[2] * Q[2] % _p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _p, G * H % _p, F * G % _p, E * H % _p)


def _mul(s: int, P: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        s >>= 1
    return Q


def _eq(P: Tuple[int, int, int, int], Q: Tuple[int, int, int, int]) -> bool:
    return (P[0] * Q[2] - Q[0] * P[2]) % _p == 0 and (P[1] * Q[2] - Q[1] * P[2]) % _p == 0


def _compress(P: Tuple[int, int, int, int]) -> bytes:
    zinv = _inv(P[2])
    x, y = P[0] * zinv % _p, P[1] * zinv % _p
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(s: bytes) -> Optional[Tuple[int, int, int, int]]:
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _p)


def _h(m: bytes) -> int:
    return int.from_bytes(hashlib.sha512(m).digest(), "little")


def _expand(secret: bytes) -> Tuple[int, bytes]:
    h = hashlib.sha512(secret).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def pure_public_key(secret: bytes) -> bytes:
    a, _ = _expand(secret)
    return _compress(_mul(a, _G))


def pure_sign(secret: bytes, msg: bytes) -> bytes:
    a, prefix = _expand(secret)
    A = _compress(_mul(a, _G))
    r = _h(prefix + msg) % _L
    R = _compress(_mul(r, _G))
    k = _h(R + A + msg) % _L
    s = (r + k * a) % _L
    return R + int.to_bytes(s, 32, "little")


def pure_verify(public: bytes, msg: bytes, sig: bytes) -> bool:
    if len(public) != 32 or len(sig) != 64:
        return False
    A = _decompress(public)
    if A is None:
        return False
    Rs = sig[:32]
    R = _decompress(Rs)
    if R is None:
        return False
    s = int.from_bytes(sig[32:], "little")
    if s >= _L:
        return False
    k = _h(Rs + public + msg) % _L
    return _eq(_mul(s, _G), _add(R, _mul(k, A)))


# ---- backend selection -------------------------------------------------------------


def _crypto():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

        return Ed25519PrivateKey, Ed25519PublicKey
    except Exception:  # pragma: no cover - depends on environment
        return None


def public_key(secret: bytes) -> bytes:
    c = _crypto()
    if c:
        from cryptography.hazmat.primitives import serialization

        k = c[0].from_private_bytes(secret).public_key()
        return k.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return pure_public_key(secret)


def sign_bytes(secret: bytes, msg: bytes) -> bytes:
    c = _crypto()
    if c:
        return c[0].from_private_bytes(secret).sign(msg)
    return pure_sign(secret, msg)


def verify_bytes(public: bytes, msg: bytes, sig: bytes) -> bool:
    c = _crypto()
    if c:
        try:
            c[1].from_public_bytes(public).verify(sig, msg)
            return True
        except Exception:
            return False
    return pure_verify(public, msg, sig)


# ---- report signing ---------------------------------------------------------------


def default_key_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(base) / "predge-ready" / "ed25519.key"


def load_or_create_key(path: Optional[str] = None) -> Tuple[bytes, Path, bool]:
    """Return (32-byte seed, path, created). The key file holds the hex seed, mode 0600."""
    p = Path(path) if path else default_key_path()
    if p.exists():
        seed = bytes.fromhex(p.read_text().strip())
        if len(seed) != 32:
            raise ValueError(f"{p} is not a 32-byte hex Ed25519 seed")
        return seed, p, False
    p.parent.mkdir(parents=True, exist_ok=True)
    seed = os.urandom(32)
    fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w") as fh:
        fh.write(seed.hex() + "\n")
    return seed, p, True


def canonical(report: Dict[str, Any]) -> bytes:
    body = {k: v for k, v in report.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def fingerprint(pub: bytes) -> str:
    return "SHA256:" + hashlib.sha256(pub).hexdigest()[:32]


def sign_report(report: Dict[str, Any], seed: bytes) -> Dict[str, Any]:
    pub = public_key(seed)
    sig = sign_bytes(seed, canonical(report))
    report["signature"] = {
        "alg": "ed25519",
        "public_key": pub.hex(),
        "fingerprint": fingerprint(pub),
        "value": sig.hex(),
        "signed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "covers": "canonical JSON of the report without this field (sorted keys, compact separators, UTF-8)",
    }
    return report


def verify_report(report: Dict[str, Any], expected_pub: Optional[str] = None) -> Tuple[bool, str]:
    s = report.get("signature")
    if not isinstance(s, dict) or s.get("alg") != "ed25519":
        return False, "report is not signed"
    try:
        pub, sig = bytes.fromhex(s["public_key"]), bytes.fromhex(s["value"])
    except (KeyError, ValueError):
        return False, "malformed signature block"
    if expected_pub:
        want = expected_pub.strip().lower()
        if want not in (pub.hex(), fingerprint(pub).lower()):
            return False, f"signed by a different key ({fingerprint(pub)})"
    if not verify_bytes(pub, canonical(report), sig):
        return False, "signature does not match: the report was modified after signing"
    return True, f"valid signature by {fingerprint(pub)} at {s.get('signed_at')}"
