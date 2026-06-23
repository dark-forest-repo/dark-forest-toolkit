"""DarkForest Signer Server — remote signing proxy.

Private keys NEVER leave the signing host. AI agents send unsigned transaction
intents; this server signs and broadcasts.

Deployment models
═════════════════

1. **Same machine** (default — most secure)
       signer binds to ``127.0.0.1``, no network exposure.
       ┌─────────────┐          ┌──────────────────┐
       │  df --signer  │  localhost  │  df-signer       │
       │  (OpenCode)  │ ──────────▶ │  --bind 127.0.0.1 │
       └─────────────┘          └──────────────────┘

2. **Secure VM** (AI cloud → your VM)
       signer binds to ``0.0.0.0`` with TLS encryption.
       ┌─────────────┐   HTTPS + Bearer  ┌────────────────────────┐
       │  df --signer  │ ────────────────▶ │  df-signer             │
       │  (AI cloud)  │   token auth      │  --bind 0.0.0.0       │
       └─────────────┘                    │  --tls-cert server.crt │
                                           │  --tls-key server.key  │
                                           └────────────────────────┘

3. **SSH tunnel** (no TLS config needed)
       ssh -L 43567:localhost:43567 user@your-vm
       # Then use DF_SIGNER_URL=http://localhost:43567 locally

Security layers
═══════════════
    Layer 1 — Network:  --bind 127.0.0.1 (default) or private subnet
    Layer 2 — Transport: TLS (--tls-cert + --tls-key) for remote access
    Layer 3 — Auth:      random Bearer token (64 hex chars, printed once)
    Layer 4 — Target:    contract allowlist (only known addresses)
    Layer 5 — Rate:      30 tx / 60s sliding window
    Layer 6 — Value:     confirm:true required above 0.1 ETH
    Layer 7 — Idle:      auto-lock after --lock-timeout seconds
    Layer 8 — Audit:     every sign event logged with timestamp + tx_hash
"""

import argparse
import http.server
import json
import os
import secrets
import sys
import time
from urllib.parse import urlparse

from web3 import Web3
from web3.middleware import geth_poa_middleware

from .keystore import KeyStore, keystore_unlock

# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

VALUE_CONFIRM_THRESHOLD = 100_000_000_000_000_000   # 0.1 ETH
RATE_LIMIT_MAX = 30                                  # tx / window
RATE_LIMIT_WINDOW = 60                               # seconds
LOCK_TIMEOUT_SEC = 3600                              # 1 hour idle → auto-lock

# Default allowlist: known game contract addresses (set at startup)
DEFAULT_ALLOW_TARGETS: list[str] = []  # populated from --proxy, --token, etc.

# ──────────────────────────────────────────────────────────────────────
# Signer
# ──────────────────────────────────────────────────────────────────────


class Signer:
    """Local signing service. Holds decrypted key in memory, never exposes it."""

    def __init__(self, rpc_url: str, gas_multiplier: float = 1.1,
                 lock_timeout: int = LOCK_TIMEOUT_SEC,
                 rate_limit: int = RATE_LIMIT_MAX,
                 confirm_threshold: int = VALUE_CONFIRM_THRESHOLD,
                 allow_targets: list[str] | None = None,
                 log_file: str | None = None):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to {rpc_url}")
        self.rpc_url = rpc_url
        self.gas_multiplier = gas_multiplier
        self.gas_limit = 2_000_000

        # ── security config ──
        self.lock_timeout = lock_timeout
        self.confirm_threshold = confirm_threshold
        self._allow_targets = [a.lower() for a in (allow_targets or [])]
        self._allow_any = len(self._allow_targets) == 0  # if none specified, allow any
        self._log_file = log_file

        # ── rate limiter (sliding window) ──
        self._rate_limit_max = rate_limit
        self._rate_window: list[float] = []  # timestamps of recent requests

        # ── state ──
        self.ks: KeyStore | None = None
        self._account_label: str | None = None
        self._local_account = None
        self.address: str | None = None
        self._last_activity: float = time.time()

        # ── API token ──
        self.api_token: str = secrets.token_hex(32)  # 64-char hex
        # Do NOT log the token to log file; only print to stdout once on startup

    # ── activity / lock ──

    def _touch(self) -> None:
        self._last_activity = time.time()

    @property
    def is_locked(self) -> bool:
        if self.lock_timeout <= 0:
            return False  # never lock
        return (time.time() - self._last_activity) > self.lock_timeout

    def check_lock(self) -> None:
        """Raise if auto-locked."""
        if self.is_locked:
            raise RuntimeError(
                "Signer is locked due to inactivity. "
                "Call POST /unlock first or restart the signer."
            )

    # ── rate limiter ──

    def check_rate_limit(self) -> None:
        if self._rate_limit_max <= 0:
            return
        now = time.time()
        # Prune old entries
        cutoff = now - RATE_LIMIT_WINDOW
        self._rate_window = [t for t in self._rate_window if t > cutoff]
        if len(self._rate_window) >= self._rate_limit_max:
            raise RuntimeError(
                f"Rate limit exceeded ({self._rate_limit_max} tx / {RATE_LIMIT_WINDOW}s). "
                "Wait or increase --rate-limit."
            )
        self._rate_window.append(now)

    # ── target allowlist ──

    def check_target(self, to_addr: str) -> None:
        if self._allow_any:
            return
        if to_addr.lower() not in self._allow_targets:
            raise RuntimeError(
                f"Target {to_addr} is not in the allowlist. "
                "Add it with --allow-target or use --allow-any-target"
            )

    # ── audit log ──

    def _audit(self, event: str, details: dict) -> None:
        """Write a structured audit line to stderr or log file."""
        entry = json.dumps({
            "ts": time.time(),
            "event": event,
            "account": self._account_label,
            "address": self.address,
            **details,
        })
        dest = self._log_file
        if dest:
            with open(dest, "a") as f:
                f.write(entry + "\n")
        else:
            print(entry, file=sys.stderr)

    # ── keystore ──

    def unlock_keystore(self, keystore_path: str | None, password: str | None) -> str:
        """Unlock the keystore and load accounts into memory.

        Caches *derived key* (not password) for re-save.
        """
        pw = password
        # Allow interactive prompt if neither password nor env var is set
        if not pw and not os.environ.get("DF_KEYSTORE_PASS"):
            import getpass
            pw = getpass.getpass("KeyStore password: ")

        self.ks = keystore_unlock(keystore_path, pw)
        self._touch()
        self._audit("keystore_unlocked", {"accounts": len(self.ks.list_accounts())})
        return f"KeyStore unlocked ({len(self.ks.list_accounts())} account(s))"

    def use_account(self, label_or_addr: str) -> str:
        """Switch to a keystore account. Decrypts the private key into memory."""
        if not self.ks:
            raise RuntimeError("KeyStore not unlocked. Call /unlock first.")
        priv_hex = self.ks.get_private_key(label_or_addr)
        self._local_account = self.w3.eth.account.from_key(priv_hex)
        self.address = self._local_account.address
        self._account_label = label_or_addr
        self._touch()
        self._audit("account_loaded", {"label": label_or_addr, "address": self.address})
        return self.address

    # ── sign & send ──

    def sign_and_send(self, to_addr: str, data_hex: str, value_wei: int = 0,
                      gas_limit: int | None = None) -> dict:
        """Build, sign, broadcast a transaction and return receipt.

        Security checks (in order):
            1. Auto-lock check
            2. Rate limit check
            3. Target allowlist check
            4. Sign and broadcast
        """
        self.check_lock()
        self.check_rate_limit()
        self.check_target(to_addr)

        if not self._local_account:
            raise RuntimeError("No account loaded. Call /use-account first.")

        gas = gas_limit or self.gas_limit
        tx = {
            "from": self.address,
            "to": Web3.to_checksum_address(to_addr),
            "value": value_wei,
            "nonce": self.w3.eth.get_transaction_count(self.address),
            "gas": gas,
            "gasPrice": int(self.w3.eth.gas_price * self.gas_multiplier),
            "chainId": self.w3.eth.chain_id,
        }
        if data_hex and data_hex != "0x":
            tx["data"] = data_hex

        signed = self._local_account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        self._touch()
        self._audit("tx_signed", {
            "to": to_addr,
            "value": value_wei,
            "tx_hash": tx_hash.hex(),
            "status": receipt["status"],
            "gas_used": receipt["gasUsed"],
            "block": receipt["blockNumber"],
        })

        return {
            "tx_hash": tx_hash.hex(),
            "block_number": receipt["blockNumber"],
            "status": receipt["status"],
            "gas_used": receipt["gasUsed"],
        }


# ──────────────────────────────────────────────────────────────────────
# HTTP request handler
# ──────────────────────────────────────────────────────────────────────

shared_signer: Signer | None = None


class SignerHandler(http.server.BaseHTTPRequestHandler):
    """Handle signing requests — NEVER expose private keys in responses.

    Security:
        - All POST routes require ``Authorization: Bearer <token>`` (except /health)
        - Bind address controls network access (--bind)
        - TLS encrypts transport (--tls-cert + --tls-key)
        - Every request is logged with source IP, method, path, status, and error detail
    """

    # Shared CORS origin from server config
    _cors_origin: str = "*"

    def log_message(self, fmt, *args):
        """Suppress default HTTP log (only use our structured access log)."""
        pass

    # ── access log ──

    def _log_access(self, status: int, detail: dict | None = None):
        """Write one structured JSON line per HTTP request.

        Every request is logged — including 401, 403, 429, 404, 500.
        This is essential for detecting scanning / attack attempts.
        """
        signer = shared_signer
        entry = {
            "ts": time.time(),
            "method": self.command,
            "path": urlparse(self.path).path,
            "ip": self.client_address[0],
            "status": status,
            "event": detail.get("event") if detail else None,
            "msg": detail.get("msg") if detail else None,
            "to": detail.get("to") if detail else None,
            "value": detail.get("value") if detail else None,
            "tx_hash": detail.get("tx_hash") if detail else None,
        }
        # Remove None fields for compactness
        entry = {k: v for k, v in entry.items() if v is not None}

        # Also write to the signer's audit log if we have one
        if signer and signer._audit and detail and detail.get("event"):
            pass  # event already logged via signer._audit()

        # Write to stderr or log file
        formatted = json.dumps(entry)
        if signer and signer._log_file:
            with open(signer._log_file, "a") as f:
                f.write(formatted + "\n")
        else:
            print(formatted, file=sys.stderr)

    # ── IP helpers ──

    @property
    def _is_local(self) -> bool:
        """True if request comes from localhost."""
        ip = self.client_address[0]
        return ip in ("127.0.0.1", "::1", "localhost")

    def _require_local(self) -> bool:
        """Reject non-local requests (for management endpoints)."""
        if not self._is_local:
            self._send_response(403, {
                "error": "this endpoint is restricted to localhost (SSH tunnel or run locally)",
            })
            return False
        return True

    # ── auth ──

    def _require_auth(self) -> bool:
        """Check Authorization header against the signer's API token.

        Logs failed attempts (important for attack detection).
        Returns True if authorized. Sends 401 response on failure.
        """
        if shared_signer is None:
            self._send_response(503, {"error": "signer not initialised"})
            return False

        # GET /health is public (no token needed for health checks)
        parsed = urlparse(self.path)
        if self.command == "GET" and parsed.path == "/health":
            return True

        auth = self.headers.get("Authorization", "")
        expected = f"Bearer {shared_signer.api_token}"

        if not auth:
            self._send_response(401, {"error": "missing Authorization header"})
            return False

        if auth != expected:
            self._send_response(401, {
                "error": "unauthorized — invalid Bearer token. "
                         "Set DF_SIGNER_TOKEN or pass --signer-token"
            })
            return False

        return True

    # ── response helpers ──

    def _json_response(self, code: int, body: dict):
        """Send HTTP JSON response and log the access.

        The access log entry includes the response body plus any extra
        detail accumulated in ``self._access_detail`` during processing.
        """
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        origin = self.headers.get("Origin", "")
        if origin and (origin == self._cors_origin or self._cors_origin == "*"):
            self.send_header("Access-Control-Allow-Origin", origin)
        else:
            self.send_header("Access-Control-Allow-Origin", self._cors_origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def _send_response(self, code: int, body: dict, extra: dict | None = None):
        """Send JSON response + log to access log with optional extra fields.

        Use this instead of _json_response for all route handlers.
        The *extra* dict can include tx_hash, to, value etc that are only
        known after the response body is constructed.
        """
        # Merge response body + extra for the access log
        log_detail = dict(body)
        if extra:
            log_detail.update(extra)
        self._json_response(code, body)
        self._log_access(code, log_detail)

    def _read_body(self) -> dict | None:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            self._send_response(400, {"error": "invalid JSON"})
            return None

    def _require_signer(self) -> Signer | None:
        if shared_signer is None:
            self._send_response(503, {"error": "signer not initialised"})
            return None
        return shared_signer

    # ── CORS preflight ──

    def do_OPTIONS(self):
        self.send_response(204)
        origin = self.headers.get("Origin", "")
        if origin and (origin == self._cors_origin or self._cors_origin == "*"):
            self.send_header("Access-Control-Allow-Origin", origin)
        else:
            self.send_header("Access-Control-Allow-Origin", self._cors_origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()
        self._log_access(204)

    # ── GET routes ──

    def do_GET(self):
        if not self._require_auth():
            return

        parsed = urlparse(self.path)
        path = parsed.path
        signer = self._require_signer()
        if signer is None:
            return

        if path == "/health":
            self._send_response(200, {
                "ok": True,
                "unlocked": signer.ks is not None,
                "locked": signer.is_locked,
                "address": signer.address,
                "account": signer._account_label,
                "rate_limit_remaining": max(0, signer._rate_limit_max - len(signer._rate_window)),
            })

        elif path == "/address":
            if not signer.address:
                self._send_response(400, {"error": "no account loaded"})
                return
            self._send_response(200, {"address": signer.address})

        elif path == "/accounts":
            if not self._require_local():
                return
            if not signer.ks:
                self._send_response(400, {"error": "keystore not unlocked"})
                return
            accounts = signer.ks.list_accounts()
            self._send_response(200, {
                "accounts": accounts,
                "current": signer._account_label,
            })

        elif path == "/token":
            if not self._require_local():
                return
            self._send_response(200, {
                "token_prefix": shared_signer.api_token[:8] + "...",
            })

        else:
            self._send_response(404, {"error": f"not found: {path}"})

    # ── POST routes ──

    def do_POST(self):
        if not self._require_auth():
            return

        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()
        if body is None and self.headers.get("Content-Length", "0") != "0":
            return  # error already sent + logged

        signer = self._require_signer()
        if signer is None:
            return

        if path == "/unlock":
            if not self._require_local():
                return
            pw = body.get("password") if body else None
            ks_path = body.get("keystore_path") if body else None
            try:
                msg = signer.unlock_keystore(ks_path, pw)
                self._send_response(200, {"event": "keystore_unlocked", "message": msg})
            except Exception as e:
                self._send_response(403, {"event": "unlock_failed", "error": str(e)})

        elif path == "/use-account":
            if not self._require_local():
                return
            label = body.get("account") if body else None
            if not label:
                self._send_response(400, {"error": "missing 'account'"})
                return
            try:
                addr = signer.use_account(label)
                self._send_response(200, {"event": "account_loaded", "address": addr})
            except Exception as e:
                self._send_response(400, {"event": "account_load_failed", "error": str(e)})

        elif path == "/sign-and-send":
            to = body.get("to") if body else None
            data = body.get("data", "0x") if body else "0x"
            value = int(body.get("value", 0)) if body else 0
            gas = body.get("gas") if body else None

            if not to:
                self._send_response(400, {"event": "sign_rejected", "error": "missing 'to'", "to": to})
                return
            if not signer.address:
                self._send_response(400, {
                    "event": "sign_rejected", "error": "no account loaded, call /use-account first",
                })
                return

            # ── value confirmation ──
            if value > signer.confirm_threshold:
                confirmed = body.get("confirm", False) if body else False
                if not confirmed:
                    self._send_response(400, {
                        "event": "sign_rejected",
                        "error": (
                            f"Value {value} exceeds confirmation threshold "
                            f"{signer.confirm_threshold}. Set confirm:true in the request body."
                        ),
                        "to": to, "value": value,
                    })
                    return

            try:
                result = signer.sign_and_send(to, data, value, gas)
                self._send_response(200, result)
            except RuntimeError as e:  # security checks (lock, rate limit, allowlist)
                self._send_response(429, {
                    "event": "sign_blocked", "error": str(e),
                    "to": to, "value": value,
                })
            except Exception as e:
                self._send_response(500, {
                    "event": "sign_failed", "error": str(e),
                    "to": to, "value": value,
                })

        elif path == "/lock":
            if not self._require_local():
                return
            if signer.ks:
                signer.ks.lock()
            signer._local_account = None
            signer.address = None
            signer._account_label = None
            signer._audit("manual_lock", {})
            self._send_response(200, {"event": "locked", "message": "signer locked"})

        else:
            self._send_response(404, {"error": f"not found: {path}"})


# ──────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        prog="df-signer",
        description="Dark Forest Signer — private keys never leave the signing host.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Deployment examples:\n"
            "\n"
            "  1) Same machine (default):\n"
            "     df-signer --rpc $RPC --account alice\n"
            "\n"
            "  2) Secure VM with TLS:\n"
            "     df-signer --rpc $RPC --account alice \\\n"
            "       --bind 0.0.0.0 --tls-cert server.crt --tls-key server.key\n"
            "\n"
            "  3) SSH tunnel (no TLS config needed):\n"
            "     ssh -L 43567:localhost:43567 user@your-vm\n"
            "     # then use DF_SIGNER_URL=http://localhost:43567\n"
        ),
    )
    parser.add_argument("--rpc", default=os.getenv("RPC_URL", "http://127.0.0.1:8545"),
                        help="BSC RPC endpoint")
    parser.add_argument("--bind", default=os.getenv("DF_SIGNER_BIND", "127.0.0.1"),
                        help="Bind address (default: 127.0.0.1). "
                             "Use 0.0.0.0 for VM deployment behind TLS.")
    parser.add_argument("--port", type=int, default=int(os.getenv("DF_SIGNER_PORT", "43567")),
                        help="Signer port (default: 43567)")
    parser.add_argument("--tls-cert", default=None,
                        help="TLS certificate file path (enables HTTPS)")
    parser.add_argument("--tls-key", default=None,
                        help="TLS private key file path")
    parser.add_argument("--allowed-origins", default="*",
                        help="CORS allowed origins (default: *, or specify e.g. https://app.darkforest.com)")
    parser.add_argument("--account", default=None,
                        help="Account label to load on startup")
    parser.add_argument("--keystore-path", default=None,
                        help="Keystore file path")
    parser.add_argument("--password", default=None,
                        help="Keystore password (omit for interactive prompt)")
    parser.add_argument("--allow-target", action="append", default=[],
                        help="Add contract address to allowlist (repeatable). "
                             "If omitted, defaults to PROXY/TOKEN/MARKET/ALLIANCE from env.")
    parser.add_argument("--allow-any-target", action="store_true",
                        help="Allow signing for ANY target address (⚠️ dangerous)")
    parser.add_argument("--lock-timeout", type=int, default=LOCK_TIMEOUT_SEC,
                        help=f"Auto-lock after N seconds idle (default: {LOCK_TIMEOUT_SEC}, 0=never)")
    parser.add_argument("--rate-limit", type=int, default=RATE_LIMIT_MAX,
                        help=f"Max transactions per minute (default: {RATE_LIMIT_MAX}, 0=unlimited)")
    parser.add_argument("--confirm-threshold", type=int, default=VALUE_CONFIRM_THRESHOLD,
                        help=f"Value threshold in wei for confirmation prompt (default: 0.1 ETH)")
    parser.add_argument("--gas-multiplier", type=float, default=1.1)
    parser.add_argument("--gas-limit", type=int, default=2_000_000)
    parser.add_argument("--log-file", default=None,
                        help="Audit log file path (default: stderr)")

    args = parser.parse_args()

    # ── build allowlist ──
    allow_targets: list[str] = []
    if args.allow_any_target:
        allow_targets = []  # empty = allow any
    elif args.allow_target:
        allow_targets = args.allow_target
    else:
        # Default: use known game contract addresses from env
        for env_var in ("PROXY_ADDR", "TOKEN_ADDR", "MARKET_ADDR", "ALLIANCE_ADDR"):
            addr = os.getenv(env_var)
            if addr:
                allow_targets.append(Web3.to_checksum_address(addr))

    # ── initialise signer ──
    global shared_signer
    try:
        signer = Signer(
            rpc_url=args.rpc,
            gas_multiplier=args.gas_multiplier,
            lock_timeout=args.lock_timeout,
            rate_limit=args.rate_limit,
            confirm_threshold=args.confirm_threshold,
            allow_targets=allow_targets,
            log_file=args.log_file,
        )
        if args.gas_limit:
            signer.gas_limit = args.gas_limit
        shared_signer = signer
        # Set CORS origin on the handler class
        SignerHandler._cors_origin = args.allowed_origins
    except ConnectionError as e:
        print(f"✗ RPC: {e}", file=sys.stderr)
        sys.exit(1)

    # ── warn about DF_KEYSTORE_PASS ──
    if os.environ.get("DF_KEYSTORE_PASS"):
        print("⚠️  WARNING: DF_KEYSTORE_PASS env var is set.", file=sys.stderr)
        print("   Other processes on this machine can read it via /proc.", file=sys.stderr)

    # ── unlock keystore ──
    try:
        msg = signer.unlock_keystore(args.keystore_path, args.password)
        print(f"✔ {msg}")
    except Exception as e:
        print(f"✗ KeyStore: {e}", file=sys.stderr)
        sys.exit(1)

    # ── load account ──
    if args.account:
        try:
            addr = signer.use_account(args.account)
            print(f"✔ Active account: {args.account} → {addr}")
        except Exception as e:
            print(f"✗ Account: {e}", file=sys.stderr)
            sys.exit(1)
    elif not signer.ks.is_empty:
        first = signer.ks.list_accounts()[0]
        addr = signer.use_account(first["label"])
        print(f"✔ Active account: {first['label']} → {addr}")

    # ── print security info ──
    proto = "https" if args.tls_cert else "http"
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║        🔐  SECURITY CONFIGURATION           ║")
    print("╠══════════════════════════════════════════════╣")
    print(f"║  API Token:    {signer.api_token[:16]}...{signer.api_token[-4:]}  ")
    print(f"║  Bind:         {args.bind}:{args.port} ({proto}){' 🔒' if args.tls_cert else ''}              ║")
    print(f"║  Auto-lock:    {args.lock_timeout}s idle                         ║")
    print(f"║  Rate limit:   {args.rate_limit} tx / {RATE_LIMIT_WINDOW}s                       ║")
    n_targets = len(allow_targets) if allow_targets else ("ANY" if args.allow_any_target else "env vars")
    print(f"║  Allowlist:    {n_targets} target(s)                      ║")
    print(f"║  Confirm >:    {args.confirm_threshold / 1e18} ETH                     ║")
    print("╠══════════════════════════════════════════════╣")
    print("║  Set these on your AI agent:                ║")
    print(f"║    export DF_SIGNER_URL={proto}://{args.bind if args.bind != '0.0.0.0' else '<VM_IP>'}:{args.port}")
    print(f"║    export DF_SIGNER_TOKEN={signer.api_token}  ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    # ── start HTTP(S) server ──
    bind_addr = args.bind
    server = http.server.HTTPServer((bind_addr, args.port), SignerHandler)

    schema = "http"
    ssl_context = None
    if args.tls_cert and args.tls_key:
        import ssl
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(args.tls_cert, args.tls_key)
        server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
        schema = "https"

    print(f"✔ Signer listening on {schema}://{bind_addr}:{args.port}")
    print(f"  Press Ctrl+C to stop")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        if signer.ks:
            signer.ks.lock()
        server.server_close()


if __name__ == "__main__":
    main()
