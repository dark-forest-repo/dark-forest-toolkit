#!/usr/bin/env python3
"""Generate abi.py from compiled forge artifacts.

Run:   python dark_forest/generate_abi.py
       forge build        # make sure contracts are compiled first

Reads contracts from the forge output directory and generates abi.py
with all function ABIs for DarkForest, DarkForestToken, EnergyMarket,
and DarkForestAlliance.
"""

import json
import os
import sys
from pathlib import Path

CONTRACTS_DIR = os.getenv(
    "CONTRACTS_DIR",
    os.path.expanduser("~/works/w3/dark-forest/packages/contracts")
)
OUT_DIR = os.path.join(CONTRACTS_DIR, "out")

# Contract name → ABI variable name + file path
CONTRACTS = {
    "DarkForest":       ("DARK_FOREST_ABI", "DarkForest.sol/DarkForest.json"),
    "DarkForestToken":  ("DFT_ABI",        "DarkForestToken.sol/DarkForestToken.json"),
    "EnergyMarket":     ("MARKET_ABI",      "EnergyMarket.sol/EnergyMarket.json"),
    "DarkForestAlliance": ("ALLIANCE_ABI",  "DarkForestAlliance.sol/DarkForestAlliance.json"),
}


def read_abi(contract_name: str, rel_path: str) -> list:
    path = os.path.join(OUT_DIR, rel_path)
    if not os.path.exists(path):
        print(f"ERROR: {path} not found. Run `forge build` in the contracts directory first.",
              file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        data = json.load(f)
    abi = data.get("abi", [])
    # Only include functions (skip constructors, events, errors for clean ABI)
    functions = [e for e in abi if e.get("type") == "function" and e.get("name", "").lower() != ""]
    # Remove internalType for web3 compatibility
    for f in functions:
        for io in f.get("inputs", []) + f.get("outputs", []):
            io.pop("internalType", None)
        # Also handle nested components (tuples)
        if f.get("outputs"):
            for out in f["outputs"]:
                if "components" in out:
                    for c in out["components"]:
                        c.pop("internalType", None)
                out.pop("internalType", None)  # also remove from output itself
        if f.get("inputs"):
            for inp in f["inputs"]:
                if "components" in inp:
                    for c in inp["components"]:
                        c.pop("internalType", None)
    return functions


def main():
    output = os.path.join(os.path.dirname(__file__), "abi.py")
    
    lines = ['"""ABI definitions — auto-generated from forge build artifacts.',
             '',
             'Run `python dark_forest/generate_abi.py` to regenerate.',
             '"""',
             '']
    
    for contract_name, (var_name, rel_path) in CONTRACTS.items():
        try:
            functions = read_abi(contract_name, rel_path)
        except SystemExit:
            raise
        
        abi_str = json.dumps(functions, indent=2)
        lines.append(f"# === {contract_name} === ({len(functions)} functions)")
        lines.append(f"{var_name} = {abi_str}")
        lines.append("")
    
    with open(output, "w") as f:
        f.write("\n".join(lines))
    
    print(f"✅ Generated {output}")
    for contract_name, (var_name, _) in CONTRACTS.items():
        funcs = [e for e in json.loads(open(output).read().split(f"{var_name} = ")[1].split("\n\n")[0])]
        print(f"   {var_name}: {len(funcs)} functions")


if __name__ == "__main__":
    main()
