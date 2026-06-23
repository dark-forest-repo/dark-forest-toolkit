#!/usr/bin/env python3
"""Generate CONTRACT_REFERENCE.md from forge build artifacts.

Reads compiled contract ABIs and extracts all external write functions
with their inputs, gas estimates, and known energy/DFT costs.
"""

import json, os, sys

CONTRACTS_DIR = os.getenv(
    "CONTRACTS_DIR",
    os.path.expanduser("~/works/w3/dark-forest/packages/contracts")
)

# Manually curated cost data (from integration testing)
COSTS: dict[str, dict] = {
    "createCivilization":   {"energy": 0, "dft": 0, "eth": "~0.01 entry fee", "gas_est": "~637k", "notes": "payable; 1 per account"},
    "collectEnergy":        {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~50k", "notes": "adds energy based on time"},
    "upgradeSystem":        {"energy": "varies", "dft": "varies", "eth": 0, "gas_est": "~300k", "notes": "need dftToken.approve first"},
    "attack":               {"energy": "3000 (lv1)", "dft": 0, "eth": 0, "gas_est": "~250k", "notes": "needs token + range"},
    "repairShield":        {"energy": "cost", "dft": 0, "eth": 0, "gas_est": "~80k", "notes": "E_ShieldFull if max"},
    "regenShield":          {"energy": "varies", "dft": 0, "eth": 0, "gas_est": "~60k", "notes": ""},
    "assistShieldRepair":   {"energy": "cost", "dft": 0, "eth": 0, "gas_est": "~80k", "notes": "alliance member only"},
    "spaceJump":            {"energy": "5000-150k", "dft": "3000-100k", "eth": 0, "gas_est": "~300k", "notes": "need dftToken.approve"},
    "trackingJump":         {"energy": "5000-150k", "dft": "3000-100k", "eth": 0, "gas_est": "~300k", "notes": "need radar + range"},
    "startMove":            {"energy": "cost", "dft": 0, "eth": 0, "gas_est": "~80k", "notes": "E_TooFar if out of range"},
    "cancelMove":           {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~30k", "notes": ""},
    "repairCollector":      {"energy": "cost", "dft": 0, "eth": 0, "gas_est": "~60k", "notes": ""},
    "repairAll":            {"energy": "varies", "dft": 0, "eth": 0, "gas_est": "~120k", "notes": "sum of all repairs"},
    "claimDailyDFT":        {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~80k", "notes": "once per day per player"},
    "claimCombatEnergy":    {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~40k", "notes": "E_NoPendingEnergy if none"},
    "rebuildCivilization":  {"energy": 5000, "dft": "varies", "eth": 0, "gas_est": "~200k", "notes": "must be ruins"},
    "approveEnergy":        {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~30k", "notes": "sets allowance"},
    "transferEnergyFrom":   {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~60k", "notes": "need allowance"},
    "batchTransferAndBurn": {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~80k", "notes": "need allowance"},
    # Market
    "createOrder":          {"energy": "amount", "dft": 0, "eth": 0, "gas_est": "~120k", "notes": "need approveEnergy"},
    "fillOrder":            {"energy": 0, "dft": "price", "eth": 0, "gas_est": "~150k", "notes": "buyer pays DFT"},
    "cancelOrder":          {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~50k", "notes": "only seller can cancel"},
    "withdrawDftFees":      {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~40k", "notes": "admin"},
    # Alliance
    "createAlliance":       {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~100k", "notes": ""},
    "joinAlliance":         {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~80k", "notes": ""},
    "leaveAlliance":        {"energy": 0, "dft": "cost", "eth": 0, "gas_est": "~100k", "notes": "need approve alliance contract"},
    "kickMember":           {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~80k", "notes": "leader only"},
    "disbandAlliance":      {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~60k", "notes": "leader only"},
    "claimRefund":          {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~40k", "notes": ""},
    # Token
    "transfer":             {"energy": 0, "dft": "amount", "eth": 0, "gas_est": "~50k", "notes": "ERC20"},
    "approve":              {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~40k", "notes": "ERC20"},
    "burn":                 {"energy": 0, "dft": "amount", "eth": 0, "gas_est": "~40k", "notes": "ERC20"},
    "burnFrom":             {"energy": 0, "dft": "amount", "eth": 0, "gas_est": "~50k", "notes": "need allowance"},
    "distributeFees":       {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~60k", "notes": "anyone can call"},
    # Admin
    "setFeeRecipient":      {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~30k", "notes": "owner only"},
    "withdrawFees":         {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~40k", "notes": "owner only"},
    "withdrawFeesTo":       {"energy": 0, "dft": 0, "eth": 0, "gas_est": "~40k", "notes": "anyone → to feeRecipient"},
}


def main():
    output_path = os.path.join(os.path.dirname(__file__), "..", "CONTRACT_REFERENCE.md")
    
    lines = [
        "# Contract Function Reference",
        "",
        "> Auto-generated from contract ABIs + integration test data.",
        "",
        "## Game Operations (DarkForest via Proxy)",
        "",
        "| Function | Inputs | Energy | DFT | ETH | Gas | Notes |",
        "|----------|--------|:------:|:---:|:---:|:---:|-------|",
    ]
    
    # Read ABI to get function inputs
    abi_path = os.path.join(CONTRACTS_DIR, "out", "DarkForest.sol", "DarkForest.json")
    try:
        with open(abi_path) as f:
            darkforest_abi = json.load(f)["abi"]
    except FileNotFoundError:
        darkforest_abi = []
    
    # Also read Market and Alliance ABIs
    market_funcs = []
    alliance_funcs = []
    try:
        with open(os.path.join(CONTRACTS_DIR, "out", "EnergyMarket.sol", "EnergyMarket.json")) as f:
            market_funcs = [e for e in json.load(f)["abi"] if e["type"] == "function"]
    except: pass
    try:
        with open(os.path.join(CONTRACTS_DIR, "out", "DarkForestAlliance.sol", "DarkForestAlliance.json")) as f:
            alliance_funcs = [e for e in json.load(f)["abi"] if e["type"] == "function"]
    except: pass
    try:
        with open(os.path.join(CONTRACTS_DIR, "out", "DarkForestToken.sol", "DarkForestToken.json")) as f:
            token_funcs = [e for e in json.load(f)["abi"] if e["type"] == "function"]
    except: pass
    
    # Game functions (write only)
    for f in darkforest_abi:
        if f.get("type") != "function" or f.get("stateMutability") in ("view", "pure"):
            continue
        name = f.get("name", "")
        if not name or name.startswith("_"):
            continue
        if name not in COSTS:
            continue
        c = COSTS[name]
        inputs = ", ".join(i["type"] for i in f.get("inputs", []))
        lines.append(f"| `{name}` | {inputs} | {c['energy']} | {c['dft']} | {c['eth']} | {c['gas_est']} | {c['notes']} |")

    # Market
    lines.append("")
    lines.append("## Energy Market")
    lines.append("")
    lines.append("| Function | Inputs | Energy | DFT | ETH | Gas | Notes |")
    lines.append("|----------|--------|:------:|:---:|:---:|:---:|-------|")
    for f in market_funcs:
        if f.get("type") != "function" or f.get("stateMutability") in ("view", "pure"):
            continue
        name = f.get("name", "")
        if name not in COSTS: continue
        c = COSTS[name]
        inputs = ", ".join(i["type"] for i in f.get("inputs", []))
        lines.append(f"| `{name}` | {inputs} | {c['energy']} | {c['dft']} | {c['eth']} | {c['gas_est']} | {c['notes']} |")

    # Alliance
    lines.append("")
    lines.append("## Alliance")
    lines.append("")
    lines.append("| Function | Inputs | Energy | DFT | ETH | Gas | Notes |")
    lines.append("|----------|--------|:------:|:---:|:---:|:---:|-------|")
    for f in alliance_funcs:
        if f.get("type") != "function" or f.get("stateMutability") in ("view", "pure"):
            continue
        name = f.get("name", "")
        if name not in COSTS: continue
        c = COSTS[name]
        inputs = ", ".join(i["type"] for i in f.get("inputs", []))
        lines.append(f"| `{name}` | {inputs} | {c['energy']} | {c['dft']} | {c['eth']} | {c['gas_est']} | {c['notes']} |")

    # Token admin
    lines.append("")
    lines.append("## DFT Token Operations")
    lines.append("")
    lines.append("| Function | Inputs | Energy | DFT | ETH | Gas | Notes |")
    lines.append("|----------|--------|:------:|:---:|:---:|:---:|-------|")
    for f in token_funcs:
        if f.get("type") != "function" or f.get("stateMutability") in ("view", "pure"):
            continue
        name = f.get("name", "")
        if name not in COSTS: continue
        c = COSTS[name]
        inputs = ", ".join(i["type"] for i in f.get("inputs", []))
        lines.append(f"| `{name}` | {inputs} | {c['energy']} | {c['dft']} | {c['eth']} | {c['gas_est']} | {c['notes']} |")

    # Energy economy
    lines.append("")
    lines.append("## Energy Economy")
    lines.append("")
    lines.append("| Parameter | Value |")
    lines.append("|-----------|-------|")
    lines.append("| `INITIAL_ENERGY` | 2000 |")
    lines.append("| `BASE_COLLECT` | 3/sec |")
    lines.append("| `DURABILITY_BASE` | 86400 (1 day) |")
    lines.append("| `ATTACK_ENERGY_BASE` | 1000 |")
    lines.append("| `ATTACK_ENERGY_PER_LV` | 2000 |")
    lines.append("| `JUMP_ENERGY_BASE` | 5000 |")
    lines.append("| `JUMP_ENERGY_PER_SQRT` | 5000 |")
    lines.append("| `JUMP_ENERGY_MAX` | 150000 |")
    lines.append("| `JUMP_DFT_BASE` | 3000 |")
    lines.append("| `JUMP_DFT_PER_SQRT` | 3000 |")
    lines.append("| `ENTRY_FEE_MIN` | 0.01 ETH |")
    lines.append("| `ENTRY_FEE_MAX` | 0.05 ETH |")
    lines.append("| `FEE_RAMP_UP_TIME` | 365 days |")
    
    with open(output_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    
    print(f"✅ Generated {output_path}")
    print(f"   {len(COSTS)} functions documented")


if __name__ == "__main__":
    main()
