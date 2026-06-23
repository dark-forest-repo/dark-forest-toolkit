#!/usr/bin/env python3
"""
Signer E2E integration test.

Architecture tested:
    Agent (signer mode) → HTTP POST /sign-and-send → Signer → anvil RPC → contract

Flow:
    1. Start anvil, deploy contracts
    2. Create keystore with deployer pk, start signer, get token
    3. Agent sends createCivilization intent via signer
    4. Agent sends collectEnergy intent
    5. Agent reads state directly from RPC
    6. Verify on-chain state changes
"""

import json, os, signal, subprocess, sys, tempfile, time
from web3 import Web3

ANVIL_PK  = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
ADDR_DEPLOY = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
CONTRACTS_DIR = os.path.expanduser("~/works/w3/dark-forest/packages/contracts")
PROXY = "0x5FC8d32690cc91D4c39d9d3abcBD16989F875707"
TOKEN = "0x5FbDB2315678afecb367f032d93F642f64180aa3"
MARKET = "0xa513E6E4b8f2a923D98304ec87F64353C4D5C853"
ALLIANCE = "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512"

PASS = 0; FAIL = 0
def check(cond, msg):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  ✅ {msg}")
    else: FAIL += 1; print(f"  ❌ {msg}")

def main():
    # ── 1. Start anvil ──
    print("\n═══ 1. Start anvil ═══")
    anvil = subprocess.Popen(
        ['anvil', '--host', '127.0.0.1', '--port', '8545', '--block-time', '1'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(4)
    w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
    check(w3.is_connected(), "anvil running")

    # ── 2. Deploy contracts ──
    print("\n═══ 2. Deploy contracts ═══")
    env = os.environ.copy(); env["PRIVATE_KEY"] = ANVIL_PK
    r = subprocess.run(
        f"forge script script/DeployDarkForest.s.sol --rpc-url http://127.0.0.1:8545 --broadcast --slow",
        shell=True, capture_output=True, text=True, cwd=CONTRACTS_DIR, env=env, timeout=60
    )
    check(r.returncode == 0, "forge deploy")

    # ── 3. Create keystore + import deployer key ──
    print("\n═══ 3. Create keystore ═══")
    from dark_forest.keystore import KeyStore
    ks_path = tempfile.mktemp(suffix=".enc")
    ks = KeyStore(ks_path)
    ks_pw = "test-e2e-pw"
    ks.create(ks_pw)
    result = ks.import_account("deployer", ANVIL_PK)
    check(result["address"].lower() == ADDR_DEPLOY.lower(), f"imported deployer key: {result['address'][:10]}...")
    ks.lock()

    # ── 4. Start signer ──
    print("\n═══ 4. Start signer ═══")
    SIGNER_PORT = "43569"
    signer_env = os.environ.copy()
    signer_env["DF_KEYSTORE_PASS"] = ks_pw
    signer_env["PROXY_ADDR"] = PROXY
    signer_env["TOKEN_ADDR"] = TOKEN
    signer_env["MARKET_ADDR"] = MARKET
    signer_env["ALLIANCE_ADDR"] = ALLIANCE

    signer = subprocess.Popen(
        [sys.executable, "-m", "dark_forest.signer_server",
         "--port", SIGNER_PORT,
         "--rpc", "http://127.0.0.1:8545",
         "--keystore-path", ks_path,
         "--account", "deployer",
         "--password", ks_pw,
         "--rate-limit", "0",  # no limits for testing
         ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=signer_env, text=True
    )

    # Read the API token from signer output (stdout or stderr)
    token = None
    deadline = time.time() + 20
    while time.time() < deadline:
        for stream in [signer.stdout, signer.stderr]:
            if not stream: continue
            line = stream.readline()
            if not line: break
            if "DF_SIGNER_TOKEN=" in line:
                token = line.strip().split("=")[-1].strip()
                break
        if token: break
    check(token is not None and len(token) == 64, f"got signer token: {token[:8]}...{token[-4:]}" if token else "no token")

    # ── 5. Create agent (signer mode) ──
    print("\n═══ 5. Create agent (signer mode) ═══")
    os.environ["DF_SIGNER_URL"] = f"http://127.0.0.1:{SIGNER_PORT}"
    os.environ["DF_SIGNER_TOKEN"] = token
    from dark_forest import DarkForestAgent
    agent = DarkForestAgent(
        "http://127.0.0.1:8545",
        signer_url=f"http://127.0.0.1:{SIGNER_PORT}",
        signer_token=token,
        proxy=PROXY, token=TOKEN, market=MARKET, alliance=ALLIANCE
    )
    check(agent._signing_mode == "signer", f"agent in signer mode: {agent.address[:10]}...")
    check(agent.address.lower() == ADDR_DEPLOY.lower(), "agent address = deployer")

    # ── 6. Set fee recipient ──
    print("\n═══ 6. Set fee recipient ═══")
    r = agent.execute("game", "setFeeRecipient", [ADDR_DEPLOY])
    check(r.get("status") == 1, "setFeeRecipient")

    # ── 7. Create civilization ──
    print("\n═══ 7. Create civilization ═══")
    fee = agent.read("game", "getEntryFee")
    r = agent.execute("game", "createCivilization", ["E2E_Civ"], value=int(fee * 102 // 100))
    check(r.get("status") == 1, f"createCiv via signer (tx: {r.get('tx_hash','')[:16]}...)")
    civ = agent.get_civilization(agent.address)
    check(civ["name"] == "E2E_Civ", f"name = {civ['name']}")
    check(civ["exists"], "civ exists")

    # ── 8. Fast-forward + collect ──
    print("\n═══ 8. Collect energy (fast-forward) ═══")
    w3.provider.make_request("evm_increaseTime", [4000])
    w3.provider.make_request("evm_mine", [])
    r = agent.execute("game", "collectEnergy")
    check(r.get("status") == 1, f"collectEnergy via signer")
    civ2 = agent.get_civilization(agent.address)
    check(civ2["energy"] > 2000, f"energy after collect+4000s = {civ2['energy']}")

    # ── 9. Batch read via agent ──
    print("\n═══ 9. Batch reads ═══")
    ss = agent.get_simple_statuses([agent.address])
    check(len(ss) == 1 and ss[0]["exists"], "getSimpleStatuses")
    pos = agent.get_positions([agent.address])
    check(len(pos) == 1, "getPositions")

    # ── 10. Cleanup ──
    print("\n═══ 10. Cleanup ═══")
    signer.send_signal(signal.SIGTERM)
    time.sleep(1)
    try: signer.kill()
    except: pass
    anvil.send_signal(signal.SIGTERM)
    time.sleep(1)
    try: anvil.kill()
    except: pass
    try: os.remove(ks_path)
    except: pass

    # ── Results ──
    total = PASS + FAIL
    print(f"\n{'═' * 50}")
    print(f"  {PASS}/{total} passed")
    if FAIL: sys.exit(1)
    print(f"  🎉 Signer E2E tests passed!")
    print(f"{'═' * 50}\n")


if __name__ == "__main__":
    main()
