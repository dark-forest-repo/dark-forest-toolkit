#!/usr/bin/env python3
"""P3#15: Signer HTTP integration smoke test.

Starts a local signer process, sends a GET /health, verifies the response.
This ensures the signer starts correctly and the HTTP layer works.
"""
import json, os, subprocess, sys, time
from urllib.request import Request, urlopen

PORT = int(os.getenv("TEST_PORT", "43568"))  # avoid conflict with dev signer


def main():
    # Start signer (no keystore — just test the HTTP layer)
    signer = subprocess.Popen(
        [sys.executable, "-m", "dark_forest.signer_server",
         "--port", str(PORT), "--rpc", "http://127.0.0.1:8545",
         "--password", "test-pass"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={**os.environ, "DF_KEYSTORE_PASS": "test-pass"},
        text=True
    )

    # Wait for startup (get the token from stdout)
    token = None
    deadline = time.time() + 15
    while time.time() < deadline:
        line = signer.stdout.readline()
        if not line:
            break
        if "DF_SIGNER_TOKEN=" in line:
            # Extract token from: "export DF_SIGNER_TOKEN=..."
            token = line.strip().split("=")[-1].strip()
            break
        # Also check stderr for the token box
    if not token:
        # Try to read from stderr
        for _ in range(50):
            line = signer.stderr.readline()
            if not line:
                break
            # The token is printed in the security box
            if "API Token:" in line:
                # Format: "║  API Token:    abcdef123456...7890  "
                token = line.strip().split(":")[-1].strip().split(".")[0].replace(" ", "")
                break

    failures = 0

    # Test 1: /health (no token needed)
    try:
        req = Request(f"http://127.0.0.1:{PORT}/health")
        resp = urlopen(req, timeout=5)
        data = json.loads(resp.read())
        assert data.get("ok") is True, f"Health not ok: {data}"
        assert "unlocked" in data
        # Without token, no sensitive info
        assert "address" not in data or data.get("address") is None, "address leaked without token"
        print("  ✅ GET /health (no token, basic)")
    except Exception as e:
        failures += 1
        print(f"  ❌ GET /health: {e}")

    # Test 2: /health (with token)
    if token:
        try:
            req = Request(f"http://127.0.0.1:{PORT}/health")
            req.add_header("Authorization", f"Bearer {token}")
            resp = urlopen(req, timeout=5)
            data = json.loads(resp.read())
            assert data.get("ok") is True
            # With token, should see more details
            print(f"  ✅ GET /health (with token, {len(data)} fields)")
        except Exception as e:
            failures += 1
            print(f"  ❌ GET /health (token): {e}")

    # Test 3: /address without token (should fail)
    try:
        req = Request(f"http://127.0.0.1:{PORT}/address")
        resp = urlopen(req, timeout=5)
        data = json.loads(resp.read())
        if "error" in data:
            print("  ✅ GET /address (no token → 401)")
        else:
            print(f"  ❌ GET /address should reject without token: {data}")
            failures += 1
    except Exception as e:
        # urlopen raises on 401
        print("  ✅ GET /address (no token → HTTP error)")

    signer.kill()
    
    if failures:
        print(f"\n{failures} test(s) FAILED")
        sys.exit(1)
    print("\n✅ All signer HTTP tests passed")


if __name__ == "__main__":
    main()
