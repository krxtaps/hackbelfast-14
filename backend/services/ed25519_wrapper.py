"""
ed25519_wrapper.py
==================
Minimal pure-Python Ed25519 implementation for key derivation and signing.

Uses only stdlib (hashlib, os).  Based on the well-known public-domain
ed25519 implementation by Brian Warner and others, reduced to just the
functions we need: derive_keypair, sign.

We do NOT verify or do batch operations — this is only for creating a
Solana wallet and signing memo transactions.
"""

import hashlib
import os

# ---------------------------------------------------------------------------
# Ed25519 constants (from RFC 8032)
# ---------------------------------------------------------------------------

P = 2 ** 255 - 19
D = -121665 * 121666 * pow(1, -1, P) % P
I = pow(2, (P - 1) // 4, P)  # sqrt(-1) mod P

B_x = 15112221349535807989036227570374659395920848912130872970408073420967665034550
B_y = 46316835694926478169428394003475163141307993866256225615783033603165251855960
B = (B_x % P, B_y % P)


def _modinv(a: int, m: int = P) -> int:
    """Modular inverse using Fermat's little theorem."""
    return pow(a, m - 2, m)


def _recover_x(y: int) -> int:
    """Recover x-coordinate from y (with sign bit)."""
    x2 = (y ** 2 - 1) * _modinv(D * y ** 2 + 1)
    x = pow(x2, (P + 3) // 8, P)
    if (x ** 2 - x2) % P != 0:
        x = (x * I) % P
    if x % 2 != 0:
        x = P - x
    return x


def _point_add(p1: tuple[int, int], p2: tuple[int, int]) -> tuple[int, int]:
    """Add two points on the twisted Edwards curve."""
    x1, y1 = p1
    x2, y2 = p2
    denom = _modinv(1 + D * x1 * x2 * y1 * y2)
    x = ((x1 * y2 + y1 * x2) * denom) % P
    y = ((y1 * y2 - x1 * x2) * denom) % P
    return (x, y)


def _point_mul(s: int, p: tuple[int, int]) -> tuple[int, int]:
    """Scalar multiplication on the curve."""
    if s == 0:
        return (0, 1)
    if s == 1:
        return p
    result = (0, 1)
    addend = p
    while s > 0:
        if s & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        s >>= 1
    return result


def _encodepoint(p: tuple[int, int]) -> bytes:
    """Encode a point as 32 bytes (y coordinate + sign bit of x)."""
    x, y = p
    y_bytes = y.to_bytes(32, "little")
    if x & 1:
        y_bytes = bytearray(y_bytes)
        y_bytes[31] |= 0x80
        y_bytes = bytes(y_bytes)
    return y_bytes


def _scalar_clamp(seed: bytes) -> int:
    """Clamp the 32-byte seed to produce a valid Ed25519 scalar."""
    # Take first 32 bytes, clamp
    h = bytearray(hashlib.sha512(seed).digest()[:32])
    h[0] &= 248
    h[31] &= 127
    h[31] |= 64
    return int.from_bytes(h, "little")


def ed25519_derive_keypair(seed: bytes) -> tuple[bytes, bytes]:
    """
    Derive an Ed25519 keypair from a 32-byte seed.

    Returns (public_key_bytes, secret_key_bytes) where:
      - public_key:  32 bytes (encoded y-coordinate)
      - secret_key:  64 bytes (seed || public_key) — standard expanded form
    """
    if len(seed) < 32:
        seed = seed + os.urandom(32 - len(seed))
    seed = seed[:32]

    a = _scalar_clamp(seed)
    aB = _point_mul(a, B)
    public_key = _encodepoint(aB)

    # Expanded secret key: seed || public_key
    secret_key = seed + public_key
    return (public_key, secret_key)


def ed25519_sign(message: bytes, secret_key: bytes) -> bytes:
    """
    Sign a message using an Ed25519 expanded secret key (64 bytes:
    seed || public_key).

    Returns the 64-byte signature (R || S).
    """
    if len(secret_key) != 64:
        raise ValueError("secret_key must be 64 bytes (seed + public_key)")

    seed = secret_key[:32]
    public_key = secret_key[32:]

    # r = SHA-512(seed[32:] || message)
    r = hashlib.sha512(seed[32:] + message).digest()
    r_int = int.from_bytes(r, "little") % P
    R = _encodepoint(_point_mul(r_int, B))

    # S = (r + SHA-512(R || public_key || message) * a) mod l
    h = hashlib.sha512(R + public_key + message).digest()
    h_int = int.from_bytes(h, "little") % P
    a = _scalar_clamp(seed)
    l = 2 ** 252 + 27742317777372353535851937790883648493  # subgroup order

    S = (r_int + h_int * a) % l
    S_bytes = S.to_bytes(32, "little")

    return R + S_bytes
