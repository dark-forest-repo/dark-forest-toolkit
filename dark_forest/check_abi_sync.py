#!/usr/bin/env python3
"""CI check — ensures abi.py is in sync with forge build artifacts.

Read-only: does NOT modify the working tree.
Exit code:  0 if ABI is in sync, 1 if abi.py needs regeneration.
"""

import os, subprocess, sys, tempfile


def main():
    current_abi_path = os.path.join(os.path.dirname(__file__), "abi.py")
    contracts_dir = os.getenv(
        "CONTRACTS_DIR",
        os.path.expanduser("~/works/w3/dark-forest/packages/contracts")
    )
    if not os.path.exists(os.path.join(contracts_dir, "out")):
        print("ERROR: Contract build artifacts not found.", file=sys.stderr)
        sys.exit(1)

    # Generate fresh ABI to a temp file (read-only check)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp_path = tmp.name
    
    result = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "generate_abi.py"),
         "--output", tmp_path],
        capture_output=True, text=True, cwd=os.path.dirname(__file__)
    )
    if result.returncode != 0:
        os.unlink(tmp_path)
        print(f"ERROR: ABI generation failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    # Compare file contents
    try:
        with open(current_abi_path) as f:
            current = f.read()
        with open(tmp_path) as f:
            generated = f.read()
    finally:
        os.unlink(tmp_path)

    if current != generated:
        print("❌ ABI is OUT OF SYNC with contracts!", file=sys.stderr)
        print("   Run:  python dark_forest/generate_abi.py", file=sys.stderr)
        sys.exit(1)

    print("✅ ABI is in sync with contracts")
    sys.exit(0)


if __name__ == "__main__":
    main()
