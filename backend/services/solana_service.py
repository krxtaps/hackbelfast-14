"""
solana_service.py
=================
Submits a memo transaction to Solana devnet using a pre-funded backend wallet.

The keypair is generated once on first run, then stored in a local JSON file
(`.solana_backend_keypair.json`).

## Funding the wallet (one-time, before demo)

  solana airdrop 2 HCeALpWEfrp8wqdv8BxmuU5tAUdmRZxJnZdcnhHak8Gb --url devnet

Or visit: https://faucet.solana.com and paste the address above.
Select "Devnet" and request a drop.

After funding, every incident report the app submits will be signed by this
wallet and recorded on-chain as a Solana memo transaction.  The user never
needs SOL.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOLANA_RPC = "https://api.devnet.solana.com"
MEMO_PROGRAM_ID = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"
KEYPAIR_FILE = Path(__file__).parent.parent / ".solana_backend_keypair.json"
KEYPAIR_FILE_PARENT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Base58 (minimal, no dependencies)
# ---------------------------------------------------------------------------

_BS58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def _bs58_decode(s: str) -> bytes:
    """Decode a base58 string."""
    n = 0
    for c in s:
        n = n * 58 + _BS58_ALPHABET.index(c)
    return n.to_bytes(32, "big")

def _bs58_encode(b: bytes) -> str:
    """Encode bytes to base58."""
    n = int.from_bytes(b, "big")
    if n == 0:
        return _BS58_ALPHABET[0]
    chars = []
    while n > 0:
        n, r = divmod(n, 58)
        chars.append(_BS58_ALPHABET[r])
    return "".join(reversed(chars))


def _load_or_create_keypair() -> dict[str, Any]:
    """Load keypair from disk or generate a new one."""
    if KEYPAIR_FILE.exists():
        data = json.loads(KEYPAIR_FILE.read_text())
        # Ensure we have both formats
        if "secret_key" in data and "public_key" in data:
            return data

    # Generate a new Ed25519 keypair using Python's stdlib only
    # (nacl/ed25519 via pure python)
    import hashlib

    # Generate 32 random bytes for the seed
    seed = os.urandom(32)

    # Simple Ed25519 key derivation.  For a real production app, use
    # the `solana` or `nacl` library.  Here we do it inline to avoid
    # dependency issues.
    # We use a well-known pure-python ed25519 implementation embedded inline.
    #
    # This follows RFC 8032 / ZIP 215 specification. The scalar is clamped
    # and multiplied by the base point to produce the public key.
    from services.ed25519_wrapper import ed25519_derive_keypair

    public_key_bytes, secret_key_bytes = ed25519_derive_keypair(seed)

    public_key_b58 = _bs58_encode(public_key_bytes)
    secret_key_b58 = _bs58_encode(secret_key_bytes)

    data = {
        "public_key": public_key_b58,
        "secret_key": secret_key_b58,
        "seed_hex": seed.hex(),
    }
    KEYPAIR_FILE.write_text(json.dumps(data, indent=2))
    return data


def get_public_key() -> str:
    """Return the base58-encoded public key of the backend wallet."""
    return _load_or_create_keypair()["public_key"]


# ---------------------------------------------------------------------------
# Transaction signing (minimal Ed25519 + Solana tx format)
# ---------------------------------------------------------------------------

def _sign_message(message_bytes: bytes, secret_key_b58: str) -> bytes:
    """Sign a message with the Ed25519 private key."""
    from services.ed25519_wrapper import ed25519_sign

    # The secret key is 64 bytes (seed || public_key), stored as base58
    # We need to decode it — but base58 decoding to a fixed 64-byte value
    # requires handling the full big integer.
    secret_bytes = _bs58_decode_raw(secret_key_b58, 64)
    signature = ed25519_sign(message_bytes, secret_bytes)
    return signature


def _bs58_decode_raw(s: str, length: int) -> bytes:
    """Decode base58 to a fixed-length byte array."""
    n = 0
    for c in s:
        n = n * 58 + _BS58_ALPHABET.index(c)
    return n.to_bytes(length, "big")


def _build_memo_tx(memo_text: str, keypair: dict[str, Any]) -> str:
    """
    Build and serialize a Solana memo transaction (legacy/unversioned format).

    The transaction is:
      - 1 signer (the backend wallet)
      - 0 account inputs (memo doesn't require signers)
      - 1 instruction (Memo program, data = memo_text)
      - recent blockhash

    Returns the base64-encoded transaction suitable for `sendTransaction`.
    """
    import base64
    import httpx

    pubkey_bytes = _bs58_decode(keypair["public_key"])
    secret_b58 = keypair["secret_key"]

    # 1. Get recent blockhash from RPC
    with httpx.Client(timeout=10) as client:
        resp = client.post(
            SOLANA_RPC,
            json={"jsonrpc": "2.0", "id": 1, "method": "getLatestBlockhash"},
        )
        result = resp.json()
        blockhash = result["result"]["value"]["blockhash"]
        bh_bytes = _bs58_decode(blockhash)

    memo_program = _bs58_decode(MEMO_PROGRAM_ID)
    memo_data = memo_text.encode("utf-8")

    # 2. Build the message (legacy format)
    # Header: 1 required sig, 0 readonly-signed, 0 readonly-unsigned
    header = bytes([1, 0, 0])

    # Addresses: fee payer (0) + memo program (1)
    addresses = pubkey_bytes + memo_program
    addr_count = bytes([2])  # compact-u16

    # Blockhash (32 bytes)
    blockhash_bytes = bh_bytes

    # Instructions: compact-u16 count + instruction(s)
    # Instruction: program_index (u8), compact-u16 account_count, u8 accounts..., compact-u16 data_len, data
    prog_idx = bytes([1])  # memo program is index 1
    acct_count = bytes([0])  # 0 accounts — memo doesn't need signers
    data_len_enc = bytes([len(memo_data)])  # compact-u16, <128
    instruction = prog_idx + acct_count + data_len_enc + memo_data
    instructions = bytes([1]) + instruction  # 1 instruction

    message = header + addr_count + addresses + blockhash_bytes + instructions

    # 3. Sign the message
    secret_bytes = _bs58_decode_raw(secret_b58, 64)
    from services.ed25519_wrapper import ed25519_sign
    signature = ed25519_sign(message, secret_bytes)

    # 4. Full transaction (unversioned): [compact-u16 sig_count] [signature] [message]
    tx = bytes([1]) + signature + message

    return base64.b64encode(tx).decode("ascii")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def submit_memo_to_solana(memo_text: str) -> dict[str, Any]:
    """
    Submit a memo transaction to Solana devnet using the backend wallet.

    Returns {"signature": str, "explorer_url": str} on success,
    or raises an exception on failure (including insufficient balance).
    """
    import httpx
    import time

    keypair = _load_or_create_keypair()
    pubkey = keypair["public_key"]

    with httpx.Client(timeout=10) as client:
        # 1. Check balance
        bal_resp = client.post(
            SOLANA_RPC,
            json={"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [pubkey]},
        )
        balance = bal_resp.json().get("result", {}).get("value", 0)
        if balance < 10000:  # need at least ~5000 lamports for fee
            raise RuntimeError(
                f"Backend wallet {pubkey} has insufficient SOL ({balance} lamports). "
                f"Please fund it via: https://faucet.solana.com (Devnet) or "
                f"run: solana airdrop 2 {pubkey} --url devnet"
            )

        # 2. Build and submit transaction
        tx_b64 = _build_memo_tx(memo_text, keypair)

        resp = client.post(
            SOLANA_RPC,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "sendTransaction",
                "params": [tx_b64, {"encoding": "base64", "skipPreflight": True}],
            },
        )
        result = resp.json()
        if "error" in result:
            raise RuntimeError(f"Solana RPC error: {result['error']}")

        sig = result["result"]

        # 3. Wait for confirmation (up to 30 seconds)
        for _ in range(30):
            time.sleep(1)
            status_resp = client.post(
                SOLANA_RPC,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getSignatureStatuses",
                    "params": [[sig]],
                },
            )
            value = status_resp.json().get("result", {}).get("value", [None])[0]
            if value is None:
                continue
            conf = value.get("confirmationStatus", "")
            if conf in ("confirmed", "finalized"):
                break
        else:
            # Timeout — transaction may still go through
            pass

        return {
            "signature": sig,
            "explorer_url": f"https://explorer.solana.com/tx/{sig}?cluster=devnet",
        }
