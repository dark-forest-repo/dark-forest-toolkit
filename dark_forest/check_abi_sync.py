#!/usr/bin/env python3
"""CI check — ensures abi.py is in sync with forge build artifacts.

Run in CI:  python dark_forest/check_abi_sync.py
Exit code:  0 if ABI is in sync, 1 if abi.py needs regeneration.
"""

import importlib, os, subprocess, sys, tempfile


def main():
    # Generate fresh ABI to a temp file
    current_abi_path = os.path.join(os.path.dirname(__file__), "abi.py")
    
    # Generate new ABI
    contracts_dir = os.getenv(
        "CONTRACTS_DIR",
        os.path.expanduser("~/works/w3/dark-forest/packages/contracts")
    )
    if not os.path.exists(os.path.join(contracts_dir, "out")):
        print("ERROR: Contract build artifacts not found.", file=sys.stderr)
        print(f"  Expected: {contracts_dir}/out/", file=sys.stderr)
        print("  Run `forge build` in the contracts directory first.", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "generate_abi.py")],
        capture_output=True, text=True, cwd=os.path.dirname(__file__)
    )
    if result.returncode != 0:
        print(f"ERROR: ABI generation failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    # Compare — just check if git would see a diff
    diff_result = subprocess.run(
        ["git", "diff", "--exit-code", current_abi_path],
        capture_output=True, text=True,
        cwd=os.path.join(os.path.dirname(__file__), "..")
    )
    
    if diff_result.returncode != 0:
        print("❌ ABI is OUT OF SYNC with contracts!", file=sys.stderr)
        print("   Run:  python dark_forest/generate_abi.py", file=sys.stderr)
        print("   Then commit the updated abi.py", file=sys.stderr)
        sys.exit(1)
    
    print("✅ ABI is in sync with contracts")
    sys.exit(0)


if __name__ == "__main__":
    main()
