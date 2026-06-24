"""DarkForest KeyStore — encrypted multi-account key management.

Inspired by sec-keys (Argon2id + AES-256-GCM), adapted for game-agent use
with labeled accounts and per-session password caching.

File layout (~/.darkforest/keystore.enc):
    {
      "version": 2,
      "kdf": { "type":"argon2id", "salt":"...", "iterations":3, "lanes":1, "memory_cost_kib":65536 },
      "nonce": "...",
      "data": "..."   ← AES-256-GCM of JSON array: [{label,private_key,address}, ...]
    }

Security properties:
    - Private keys never written to disk in plaintext.
    - Password entered via getpass (not shell history) or DF_KEYSTORE_PASS env var.
    - Decrypted keys held in memory only; caller must .lock() to clear.
    - File permissions set to 0o600 (owner read/write only).
"""

import base64
import getpass
import json
import os
import secrets
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from Crypto.Hash import keccak

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ARGON2_SALT_LEN = 16
_ARGON2_ITERATIONS = 3
_ARGON2_LANES = 1
_ARGON2_MEM_COST = 64 * 1024  # 64 MiB (in KiB)
_AES_NONCE_LEN = 12
_AES_KEY_LEN = 32

_SECP256K1_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_CONTAINER_VERSION = 2

DEFAULT_KEYSTORE_PATH = str(Path.home() / ".darkforest" / "keystore.enc")


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------

def generate_private_key() -> bytes:
    """Return a cryptographically random 32-byte secp256k1 private key."""
    while True:
        key_bytes = secrets.token_bytes(32)
        key_int = int.from_bytes(key_bytes, "big")
        if 0 < key_int < _SECP256K1_ORDER:
            return key_bytes


def private_key_to_address(key_bytes: bytes) -> str:
    """Derive 0x-prefixed Ethereum address from raw private key bytes."""
    key_int = int.from_bytes(key_bytes, "big")
    priv = ec.derive_private_key(key_int, ec.SECP256K1())
    pub = priv.public_key()
    from cryptography.hazmat.primitives import serialization
    pub_bytes = pub.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    h = keccak.new(digest_bits=256)
    h.update(pub_bytes[1:])
    return "0x" + h.digest()[-20:].hex()


def _private_key_hex(key_bytes: bytes) -> str:
    return "0x" + key_bytes.hex()


# ---------------------------------------------------------------------------
# Encryption / decryption
# ---------------------------------------------------------------------------

def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = Argon2id(salt, _AES_KEY_LEN, _ARGON2_ITERATIONS, _ARGON2_LANES, _ARGON2_MEM_COST)
    return kdf.derive(password.encode("utf-8"))


def encrypt_data(plaintext: str, password: str) -> tuple[bytes, bytes, bytes]:
    """Return (salt, nonce, ciphertext_with_tag)."""
    salt = os.urandom(_ARGON2_SALT_LEN)
    nonce = os.urandom(_AES_NONCE_LEN)
    key = _derive_key(password, salt)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return salt, nonce, ct


def decrypt_data(ciphertext: bytes, password: str, salt: bytes, nonce: bytes) -> str:
    key = _derive_key(password, salt)
    return AESGCM(key).decrypt(nonce, ciphertext, None).decode("utf-8")


# ---------------------------------------------------------------------------
# KeyStore
# ---------------------------------------------------------------------------

class KeyStore:
    """Encrypted, password-protected store for labeled Ethereum accounts.

    Usage::

        ks = KeyStore()                        # ~/.darkforest/keystore.enc
        if not ks.exists():
            ks.create("my-secure-password")     # first-time setup
        ks.unlock("my-secure-password")         # decrypt into memory

        ks.add_account("alice")                 # generate + save
        ks.import_account("bob", "0x...")       # import existing key
        priv = ks.get_private_key("alice")      # hex string, in memory
        ks.list_accounts()                      # [(label, address), ...]
        ks.remove_account("bob")

        ks.lock()                               # clear memory
    """

    def __init__(self, path: str | None = None):
        self.path = path or DEFAULT_KEYSTORE_PATH
        self._accounts: list[dict] | None = None  # None = locked
        self._cache_key: bytearray | None = None  # mutable for zeroing on lock()

    # ── file ops ──

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def create(self, password: str | None = None) -> None:
        """Initialise a new (empty) keystore.

        If *password* is None, prompts interactively.
        """
        if self.exists():
            raise FileExistsError(f"KeyStore already exists: {self.path}")

        pw = password or _prompt_password_confirm()
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        self._accounts = []
        # First save: need password + fresh salt to build KDF metadata
        salt = os.urandom(_ARGON2_SALT_LEN)
        self._cache_key = bytearray(_derive_key(pw, salt))
        plain = json.dumps(self._accounts, separators=(",", ":"))
        nonce = os.urandom(_AES_NONCE_LEN)
        ct = AESGCM(self._cache_key).encrypt(nonce, plain.encode("utf-8"), None)
        container = {
            "version": _CONTAINER_VERSION,
            "kdf": {
                "type": "argon2id",
                "salt": base64.b64encode(salt).decode(),
                "iterations": _ARGON2_ITERATIONS,
                "lanes": _ARGON2_LANES,
                "memory_cost_kib": _ARGON2_MEM_COST,
            },
            "nonce": base64.b64encode(nonce).decode(),
            "data": base64.b64encode(ct).decode(),
        }
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(container, f, separators=(",", ":"))
        _chmod_600(self.path)

    def unlock(self, password: str | None = None) -> None:
        """Decrypt keystore into memory.

        Password sources (in order):
          1. *password* argument
          2. ``DF_KEYSTORE_PASS`` env var (⚠️ insecure, leaks via /proc)
          3. Interactive ``getpass`` prompt

        Caches the *derived key* (not the password) for re-save.
        """
        pw = password or os.environ.get("DF_KEYSTORE_PASS") or _prompt_password()
        # Parse container to get salt before deriving key
        with open(self.path) as f:
            container = json.load(f)
        kdf_info = container["kdf"]
        salt = base64.b64decode(kdf_info["salt"])
        # Derive and cache key (not password)
        self._cache_key = bytearray(_derive_key(pw, salt))
        self._load_with_cache(container)  # decrypt using cached key

    def lock(self) -> None:
        """Clear all decrypted keys and cached key from memory.

        Overwrites the in-memory key buffer before releasing the reference.
        Best-effort: Python strings are immutable but the derived key buffer
        is explicitly zeroed.
        """
        # Zero the derived key buffer
        if self._cache_key is not None:
            self._cache_key[:] = b"\x00" * len(self._cache_key)
        self._cache_key = None
        self._accounts = None

    @property
    def unlocked(self) -> bool:
        return self._accounts is not None

    @property
    def is_empty(self) -> bool:
        return self.unlocked and len(self._accounts) == 0

    def require_unlocked(self):
        if not self.unlocked:
            raise RuntimeError("KeyStore is locked. Call .unlock() first.")

    # ── account management ──

    def add_account(self, label: str) -> dict:
        """Generate a new private key, label it, persist and return ``{label, address}``."""
        self.require_unlocked()
        _validate_label(label, [a["label"] for a in self._accounts])
        raw = generate_private_key()
        entry = {
            "label": label,
            "private_key": _private_key_hex(raw),
            "address": private_key_to_address(raw),
        }
        self._accounts.append(entry)
        self._save_with_cache()
        return {"label": entry["label"], "address": entry["address"]}

    def import_account(self, label: str, private_key_hex: str) -> dict:
        """Import an existing private key under *label*.

        *private_key_hex* may or may not include the ``0x`` prefix.
        """
        self.require_unlocked()
        _validate_label(label, [a["label"] for a in self._accounts])
        raw_hex = private_key_hex.removeprefix("0x")
        raw = bytes.fromhex(raw_hex)
        if len(raw) != 32:
            raise ValueError("Private key must be 32 bytes (64 hex chars)")
        entry = {
            "label": label,
            "private_key": "0x" + raw_hex,
            "address": private_key_to_address(raw),
        }
        self._accounts.append(entry)
        self._save_with_cache()
        return {"label": entry["label"], "address": entry["address"]}

    def remove_account(self, label: str) -> None:
        """Remove an account by label."""
        self.require_unlocked()
        before = len(self._accounts)
        self._accounts = [a for a in self._accounts if a["label"] != label]
        if len(self._accounts) == before:
            raise KeyError(f"Account {label!r} not found in keystore")
        self._save_with_cache()

    def get_private_key(self, label_or_addr: str) -> str:
        """Return the hex private key for the matching account.

        Matches by label first, then by address (case-insensitive).
        """
        self.require_unlocked()
        entry = self._find(label_or_addr)
        if entry is None:
            raise KeyError(f"No account matching {label_or_addr!r} in keystore")
        return entry["private_key"]

    def get_address(self, label_or_addr: str) -> str:
        """Return the address for the matching account."""
        self.require_unlocked()
        entry = self._find(label_or_addr)
        if entry is None:
            raise KeyError(f"No account matching {label_or_addr!r} in keystore")
        return entry["address"]

    def list_accounts(self) -> list[dict]:
        """Return list of ``{label, address}`` — **no private keys**."""
        self.require_unlocked()
        return [{"label": a["label"], "address": a["address"]} for a in self._accounts]

    # ── internals ──

    def _find(self, label_or_addr: str) -> dict | None:
        needle = label_or_addr.lower()
        for a in self._accounts:
            if a["label"] == label_or_addr or a["address"].lower() == needle:
                return a
        return None

    def _load_with_cache(self, container: dict) -> None:
        """Decrypt using cached derived key (not password)."""
        nonce = base64.b64decode(container["nonce"])
        ct = base64.b64decode(container["data"])
        key = self._cache_key
        plain = AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")
        self._accounts = json.loads(plain)

    def _save_with_cache(self) -> None:
        """Re-encrypt and save using cached key (file must already exist).

        Reads existing container to preserve KDF metadata (salt, params).
        """
        if not self._cache_key:
            raise RuntimeError("KeyStore cache key not set — call unlock() first")

        plain = json.dumps(self._accounts, separators=(",", ":"))
        nonce = os.urandom(_AES_NONCE_LEN)
        ct = AESGCM(self._cache_key).encrypt(nonce, plain.encode("utf-8"), None)

        # Read existing container to preserve KDF metadata
        with open(self.path) as f:
            existing = json.load(f)

        container = {
            "version": _CONTAINER_VERSION,
            "kdf": existing["kdf"],
            "nonce": base64.b64encode(nonce).decode(),
            "data": base64.b64encode(ct).decode(),
        }
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(container, f, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_label(label: str, existing: list[str]) -> None:
    if not label or "/" in label or "\\" in label:
        raise ValueError(f"Invalid label: {label!r} (must be non-empty, no slashes)")
    if label in existing:
        raise ValueError(f"Label {label!r} already exists in keystore")


def _prompt_password() -> str:
    pw = getpass.getpass("KeyStore password: ")
    if not pw:
        print("Password cannot be empty.", file=sys.stderr)
        sys.exit(1)
    return pw


def _prompt_password_confirm() -> str:
    pw = getpass.getpass("New KeyStore password: ")
    if not pw:
        print("Password cannot be empty.", file=sys.stderr)
        sys.exit(1)
    confirm = getpass.getpass("Confirm password: ")
    if pw != confirm:
        print("Passwords do not match.", file=sys.stderr)
        sys.exit(1)
    return pw


def _chmod_600(path: str) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # best effort on platforms that don't support it


# ---------------------------------------------------------------------------
# CLI integration helpers (used by cli.py)
# ---------------------------------------------------------------------------

def keystore_init(path: str | None, password: str | None) -> KeyStore:
    """Create a new keystore (ask password interactively if not given)."""
    ks = KeyStore(path)
    if ks.exists():
        print(f"✗ KeyStore already exists: {ks.path}", file=sys.stderr)
        sys.exit(1)
    ks.create(password)
    print(f"✔ KeyStore created: {ks.path}")
    return ks


def keystore_unlock(path: str | None, password: str | None) -> KeyStore:
    """Unlock an existing keystore and return it."""
    ks = KeyStore(path)
    if not ks.exists():
        print(f"✗ KeyStore not found: {ks.path}", file=sys.stderr)
        print("  Run: df-ks init  to create one", file=sys.stderr)
        sys.exit(1)
    ks.unlock(password)
    return ks
