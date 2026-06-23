# Architecture Design

## System Overview

```
┌─────────────────────────────────────┐        ┌──────────────────────────────┐
│         AI Cloud (OpenCode)         │        │    Your Secure Machine        │
│                                     │        │                              │
│  ┌───────────────────────────────┐  │ HTTPS  │  ┌────────────────────────┐  │
│  │  dark_forest/agent.py         │  │───────▶│  │  signer_server.py      │  │
│  │  ┌─────────┐ ┌──────────────┐ │  │ Bearer │  │  ┌──────────────────┐ │  │
│  │  │ execute  │ │    read()    │ │  │ token  │  │  │    Signer class  │ │  │
│  │  │  ABI     │ │  eth_call    │─┼──┼────────┼─▶│  │  ┌────────────┐ │ │  │
│  │  │  encode  │ │  (direct)    │ │  │        │  │  │  │  KeyStore   │ │ │  │
│  │  └────┬─────┘ └──────┬───────┘ │  │        │  │  │  │  (encrypted)│ │ │  │
│  │       │              │          │  │        │  │  │  └────────────┘ │ │  │
│  │  {to, data, value}   │          │  │        │  │  └──────────────────┘ │  │
│  └───────┼──────────────┼──────────┘  │        │  └────────────────────────┘  │
│          │              │              │        │                              │
└──────────┼──────────────┼──────────────┘        └──────────────┬───────────────┘
           │              │                                      │
           │              │         ┌────────────────────────────┘
           │              │         │
           ▼              ▼         ▼
    ┌──────────────────────────────────┐
    │          BSC RPC Node            │
    │  eth_sendRawTransaction          │
    │  eth_call                        │
    └──────────────────────────────────┘
```

## Component Responsibilities

### Agent (`dark_forest/agent.py`)
- **Knows**: game logic (which contract, which function, what parameters)
- **Does**: ABI-encodes function calls, sends intents to signer, queries chain state
- **Does NOT**: sign transactions, hold private keys, manage accounts
- **Trusts**: signer URL + token, contract ABI accuracy

### Signer (`dark_forest/signer_server.py`)
- **Knows**: encrypted keystore, account labels, API token
- **Does**: decrypt keys in memory, build+sign+broadcast transactions, enforce security policies
- **Security layers**: bind address → TLS → token auth → target allowlist → rate limit → value confirmation → auto-lock → audit log
- **Does NOT**: know game logic, expose private keys, allow unrestricted signing

### KeyStore (`dark_forest/keystore.py`)
- **Encryption**: Argon2id (64 MiB, 3 rounds) → AES-256-GCM
- **Storage**: `~/.darkforest/keystore.enc`, permissions 600
- **Memory**: password never cached; derived AES key cached as `bytearray`, zeroed on lock
- **Multi-account**: labeled accounts, import/export, address-only export for safe sharing

### CLI (`dark_forest/cli.py`)
- **Modes**: local signing (`--key`), keystore signing (`--account`), remote signer (`--signer`)
- **Commands**: `execute`, `read`, `ks`, shortcuts (`create-civ`, `attack`, `collect`, ...)

## Data Flow

### Write Transaction Flow
```
1. CLI:      df --signer create-civ "MyCiv"
2. Agent:    data = encodeABI("createCivilization", ["MyCiv"])
3. Agent:    POST /sign-and-send {"to": proxy, "data": "0x...", "value": "0x2386f26fc10000"}
4. Signer:   check_lock() → check_rate() → check_target(proxy)
5. Signer:   tx = build_tx(from=addr, to=proxy, data="0x...", value=..., nonce=..., gas=..., gasPrice=...)
6. Signer:   signed = account.sign_transaction(tx)
7. Signer:   send_raw_transaction(signed) → RPC
8. Signer:   wait_for_receipt() → return {tx_hash, block_number, status, gas_used}
9. Agent:    return receipt to CLI
```

### Read Flow
```
1. CLI:      df status 0x...
2. Agent:    eth_call → RPC → decode → return structured dict
3. CLI:      print JSON
```

## Security Boundaries

| Boundary | Mechanism | Attacker Must |
|----------|-----------|--------------|
| Network | `--bind 127.0.0.1` or private subnet | be on the same machine/VPN |
| Transport | TLS (`--tls-cert` + `--tls-key`) | MITM is harder |
| Auth | Random 64-char Bearer token, printed once | steal the token |
| Target | Contract allowlist (Proxy, Token, Market, Alliance) | know a whitelisted contract |
| Rate | 30 tx / 60s sliding window | wait or increase limit |
| Value | >0.1 ETH needs `confirm:true` | know the threshold |
| Idle | Auto-lock after `--lock-timeout` (1h) | re-unlock the keystore |
| Memory | `bytearray` zeroed on lock | dump memory before lock |
| Audit | Every request logged with IP + status | leave no trace |

## Trust Model

```
Agent (AI cloud)
  ├── Trusts: signer will validate + sign + broadcast
  ├── Trusts: contract ABIs are correct
  ├── Risk: if token stolen → attacker can send game intents
  │         → but target allowlist + rate limit + value confirm limit damage
  └── Cannot: read private keys, sign arbitrary txs, drain wallets

Signer (your machine)
  ├── Trusts: RPC node is honest
  ├── Trusts: local filesystem is not compromised
  ├── Risk: if machine compromised → keys exposed regardless
  └── Mitigation: auto-lock, audit log, no password in memory

KeyStore (file on disk)
  ├── Trusts: Argon2id + AES-256-GCM are unbroken
  ├── Trusts: password is strong and not shared
  ├── Risk: brute-force if weak password
  └── Mitigation: Argon2id memory-hard KDF (64 MiB), no online key material
```

## Deployment Models

### 1. Same Machine (development)
```
Agent + Signer both on localhost:43567
No TLS needed, token auth only
```

### 2. Secure VM (production)
```
Agent on AI cloud → HTTPS → Signer on VM (--bind 0.0.0.0, --tls-cert)
SSH port forwarding as fallback
```

### 3. SSH Tunnel (simple remote)
```
ssh -L 43567:localhost:43567 user@vm
# Agent connects to localhost:43567 (tunneled to VM)
```
