# Dark Forest — Python Agent + Signer

On-chain MMO game: Python agent, CLI, encrypted keystore, and secure remote signing proxy.

> ## ⚠️ DISCLAIMER
>
> **This software is provided "as is", without warranty of any kind, express or implied.**
>
> ### 1. Understand Before You Use
> Do not use this software unless you fully understand its source code, mechanisms, and
> security model. You are responsible for reading, compiling, and verifying every line of
> code that handles your private keys, transaction signing, and fund movements.
>
> ### 2. No Perfect Security
> No software, tool, or runtime environment is 100% secure. The security features in this
> project (encrypted keystore, TLS, token auth, rate limiting, etc.) reduce risk but do
> **not** eliminate it. Risks include but are not limited to:
>   - Compromise of the machine where the signer or keystore runs
>   - Memory inspection by malicious processes with sufficient privileges
>   - Side-channel attacks, supply-chain attacks, or zero-day vulnerabilities in
>     dependencies (Python, OpenSSL, cryptography libraries, OS kernel, etc.)
>   - Social engineering, phishing, or token theft
>   - Misconfiguration by the user (e.g., binding to `0.0.0.0` without TLS,
>     using `--allow-any-target`, setting weak passwords)
>
> ### 3. Fund Safety
> **Only use this software with funds you are willing to lose entirely.** Blockchain
> transactions are irreversible. A single misconfiguration, bug, or security breach can
> result in the total loss of all assets controlled by the keys managed through this
> software. The developers, contributors, and affiliated parties assume **no liability**
> for any direct, indirect, incidental, or consequential losses.
>
> ### 4. Smart Contract Risk
> This tool interacts with smart contracts on blockchain networks. Smart contracts may
> contain bugs, be subject to exploits, or behave in unexpected ways. This tool does
> not mitigate those risks.
>
> ### 5. Audit Scope
> Third-party security audits (if any) are snapshots in time and do not guarantee the
> absence of vulnerabilities. Audits may not cover all dependencies, deployment
> configurations, or future code changes.
>
> ### 6. No Financial Advice
> Nothing in this software or its documentation constitutes financial, legal, or
> investment advice. You alone bear responsibility for your decisions.
>
> **By using this software, you acknowledge that you have read, understood, and
> agreed to these terms. If you do not agree, do not use this software.**
>
> ---

## Architecture

```
                         AI Cloud                    Your Machine
┌──────────────────────────────────────┐   ┌──────────────────────────────────────┐
│  df (CLI / Agent)                    │   │  df-signer                           │
│                                      │   │                                      │
│  execute("game", "attack", [addr])   │──▶│  POST /sign-and-send                 │
│  read("game", "getCivilization")     │   │  {to, data, value}                   │
│                                      │   │                                      │
│  No private key                      │   │  ✓ Token auth    ✓ Target allowlist  │
│  No signing logic                    │   │  ✓ Auto-lock     ✓ Rate limiting     │
│  Just ABI encoding + eth_call        │   │  ✓ Audit log     ✓ TLS support       │
└──────────────────────────────────────┘   │  ✓ Encrypted keystore (Argon2id+AES) │
                                           └──────────────────────────────────────┘
```

## Install

```bash
pip install web3 cryptography pycryptodome
```

Or from source:

```bash
pip install -e .
```

## Quick Start

### Mode 1: Remote signer (recommended — private key stays on your machine)

```bash
# Terminal 1 — start the signer
df-signer --rpc https://bsc-dataseed.binance.org --account alice
#  Copy the DF_SIGNER_TOKEN from output

# Terminal 2 — send intents
export DF_SIGNER_URL=http://localhost:43567
export DF_SIGNER_TOKEN=abc123...   # paste from step 1

df create-civ "MyCiv"
df collect
df attack 0xTarget...
df status
```

### Mode 2: Local signing (legacy, not for cloud use)

```bash
df --key 0x... --rpc https://... create-civ "MyCiv"
```

## Keystore Management

```bash
df ks init              # create encrypted keystore
df ks add alice         # generate new key
df ks import bob 0x...  # import existing key
df ks list              # list accounts (addresses only)
df ks export-addresses  # safe to share
```

## Generic API (any contract function)

```bash
df execute game createCivilization "MyCiv" --value 100000000000000000
df read game getCivilization 0x...
df execute token balanceOf 0x...
df execute market createOrder 100 50
```

## Python SDK

```python
from dark_forest import DarkForestAgent

agent = DarkForestAgent(
    rpc_url="https://bsc-dataseed.binance.org",
    signer_url="http://localhost:43567",
    signer_token="xxx",
    proxy="0x...", token="0x...", market="0x...", alliance="0x...",
)

# Generic
agent.execute("game", "createCivilization", ["MyCiv"], value=1e17)
agent.read("game", "getCivilization", ["0x..."])

# Batch reads (2 RPC calls instead of 6N)
agent.statuses(["0x...", "0x..."])
agent.get_positions(["0x...", "0x..."])

# Backward compat
agent.create_civilization("MyCiv")
agent.attack("0x...")
agent.collect_energy()
```

## Security Features

| Layer | Feature | Default |
|-------|---------|---------|
| 1 | Network bind (`--bind`) | `127.0.0.1` |
| 2 | TLS transport (`--tls-cert/key`) | disabled |
| 3 | Bearer token auth (64-char hex) | auto-generated |
| 4 | Target contract allowlist | env vars |
| 5 | Rate limiting | 30 tx / 60s |
| 6 | Value confirmation (>0.1 ETH) | `confirm:true` required |
| 7 | Auto-lock on idle | 1 hour |
| 8 | Audit log (per-request) | stderr or `--log-file` |

## Deploy on Secure VM

```bash
df-signer \
  --rpc https://bsc-dataseed.binance.org \
  --bind 0.0.0.0 \
  --tls-cert /etc/ssl/server.crt \
  --tls-key /etc/ssl/server.key \
  --account alice \
  --log-file /var/log/df-signer.log
```

## Requirements

- Python 3.10+
- `web3` — EVM interaction
- `cryptography` — Argon2id + AES-256-GCM
- `pycryptodome` — keccak256 (Ethereum address derivation)
