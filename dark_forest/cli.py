#!/usr/bin/env python3
"""Dark Forest CLI — command-line interface to all game functions.

Usage::

    # Generic (always works for any contract function)
    df execute game createCivilization "MyCiv" --value 100000000000000000
    df read game getCivilization 0x...

    # Shortcuts (less typing for common commands)
    df create-civ "MyCiv"
    df attack 0x...
    df collect
    df status 0x...

    # Keystore management
    df ks init
    df ks list
    df ks add bob

    # Using remote signer
    DF_SIGNER_URL=http://localhost:43567 DF_SIGNER_TOKEN=abc... df collect
"""

import json
import os
import sys

from .agent import DarkForestAgent, SYSTEM_NAMES
from .keystore import keystore_init, keystore_unlock


def print_json(data):
    print(json.dumps(data, indent=2, default=str))


def _build_agent(args) -> DarkForestAgent:
    return DarkForestAgent(
        rpc_url=args.rpc,
        signer_url=args.signer or os.environ.get("DF_SIGNER_URL"),
        signer_token=args.signer_token or os.environ.get("DF_SIGNER_TOKEN"),
        private_key=args.key,
        account=args.account,
        keystore_path=args.keystore_path,
        keystore_password=os.environ.get("DF_KEYSTORE_PASS"),
        proxy=args.proxy, token=args.token,
        market=args.market, alliance=args.alliance,
    )


# ══════════════════════════════════════════════════════════════════════════
# Main CLI
# ══════════════════════════════════════════════════════════════════════════


def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog="df",
        description="Dark Forest Agent CLI",
    )
    parser.add_argument("--rpc", default=os.getenv("RPC_URL", "http://127.0.0.1:8545"))
    parser.add_argument("--key", default=os.getenv("PRIVATE_KEY", ""),
                        help="Plaintext private key (legacy)")
    parser.add_argument("--account", default=None,
                        help="Account label from keystore (local signing)")
    parser.add_argument("--signer", default=os.getenv("DF_SIGNER_URL"),
                        help="Remote signer URL")
    parser.add_argument("--signer-token", default=None,
                        help="Signer API token")
    parser.add_argument("--keystore-path", default=None)
    parser.add_argument("--proxy", default=os.getenv("PROXY_ADDR", ""))
    parser.add_argument("--token", default=os.getenv("TOKEN_ADDR", ""))
    parser.add_argument("--market", default=os.getenv("MARKET_ADDR", ""))
    parser.add_argument("--alliance", default=os.getenv("ALLIANCE_ADDR", ""))
    parser.add_argument("--json", action="store_true")

    sub = parser.add_subparsers(dest="cmd", required=False)

    # ── generic execute / read ──
    p = sub.add_parser("execute", help="Execute a write transaction (generic)")
    p.add_argument("contract", type=str, help="game / token / market / alliance")
    p.add_argument("func", type=str, help="Function name")
    p.add_argument("args", type=str, nargs="*", help="Function arguments")
    p.add_argument("--value", type=int, default=0, help="msg.value in wei")

    p = sub.add_parser("read", aliases=["call"], help="Read contract state (generic)")
    p.add_argument("contract", type=str)
    p.add_argument("func", type=str)
    p.add_argument("args", type=str, nargs="*")

    # ── keystore ──
    _add_keystore_sub(sub)

    # ── shortcuts ──
    p = sub.add_parser("create-civ", help="Create civilization")
    p.add_argument("name", type=str)
    p.add_argument("--referrer", type=str, default=None)
    p.add_argument("--fee", type=int, default=None)

    p = sub.add_parser("upgrade", help="Upgrade system (0-4)")
    p.add_argument("sys_id", type=int)

    sub.add_parser("collect", help="Collect energy")

    p = sub.add_parser("attack", help="Attack target")
    p.add_argument("target", type=str)

    p = sub.add_parser("repair-shield", help="Repair shield")
    p.add_argument("amount", type=int)
    sub.add_parser("regen-shield", help="Regen shield")
    sub.add_parser("repair-all", help="Repair all durability")

    sub.add_parser("jump", help="Space jump")
    p = sub.add_parser("tracking-jump", help="Tracking jump")
    p.add_argument("target", type=str)

    p = sub.add_parser("move", help="Start cruise")
    p.add_argument("x", type=int)
    p.add_argument("y", type=int)
    p.add_argument("z", type=int)
    sub.add_parser("cancel-move", help="Cancel cruise")

    sub.add_parser("claim-dft", help="Claim daily DFT")
    sub.add_parser("withdraw-fees", help="Withdraw fees (owner)")

    p = sub.add_parser("create-order", help="List energy for sale")
    p.add_argument("energy", type=int)
    p.add_argument("price", type=int)
    p = sub.add_parser("fill-order", help="Buy energy")
    p.add_argument("order_id", type=int)
    p = sub.add_parser("cancel-order", help="Cancel order")
    p.add_argument("order_id", type=int)
    sub.add_parser("orders", help="List active orders")

    p = sub.add_parser("civ", help="Get civilization info")
    p.add_argument("player", type=str, default=None, nargs="?")
    p = sub.add_parser("status", help="Full status snapshot")
    p.add_argument("player", type=str, default=None, nargs="?")
    p = sub.add_parser("statuses", aliases=["civs"], help="Batch status")
    p.add_argument("players", type=str, nargs="+")
    sub.add_parser("entry-fee", help="Get entry fee")
    p = sub.add_parser("battles", help="Get battle history")
    p.add_argument("--limit", type=int, default=10)
    p = sub.add_parser("position", help="Get position")
    p.add_argument("player", type=str, default=None, nargs="?")

    p = sub.add_parser("balance", help="Get DFT balance")
    p.add_argument("player", type=str, default=None, nargs="?")
    p = sub.add_parser("approve", help="Approve DFT")
    p.add_argument("spender", type=str)
    p.add_argument("amount", type=int)

    p = sub.add_parser("whoami", help="Show current account")

    args = parser.parse_args()

    # ── keystore commands ──
    if args.cmd in ("keystore", "ks"):
        _handle_keystore(args)
        return

    if not args.cmd:
        parser.print_help()
        return

    # ── build agent ──
    try:
        agent = _build_agent(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # ── route command ──
    try:
        _route(args, agent)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _route(args, agent: DarkForestAgent):
    """Route CLI commands — shortcuts call agent methods, most just use execute/read."""

    # ── generic execute ──
    if args.cmd == "execute":
        parsed = [_try_int(a) for a in args.args]
        r = agent.execute(args.contract, args.func, parsed, value=args.value)
        print_json(r)
        return

    # ── generic read ──
    if args.cmd in ("read", "call"):
        parsed = [_try_int(a) for a in args.args]
        r = agent.read(args.contract, args.func, parsed)
        print_json(r)
        return

    # ── shortcuts ──
    if args.cmd == "create-civ":
        r = agent.create_civilization(args.name, args.referrer, args.fee)
        print(f"Tx: {r['tx_hash']}")

    elif args.cmd == "upgrade":
        r = agent.upgrade_system(args.sys_id)
        print(f"Upgraded {SYSTEM_NAMES.get(args.sys_id, args.sys_id)}: {r['tx_hash']}")

    elif args.cmd == "collect":
        r = agent.collect_energy()
        print(f"Collected: {r['tx_hash']}")

    elif args.cmd == "attack":
        r = agent.attack(args.target)
        print(f"Attack: {r['tx_hash']}")

    elif args.cmd == "repair-shield":
        r = agent.repair_shield(args.amount)
        print(f"Shield repaired: {r['tx_hash']}")

    elif args.cmd == "regen-shield":
        r = agent.regen_shield()
        print(f"Regen: {r['tx_hash']}")

    elif args.cmd == "repair-all":
        r = agent.repair_all()
        print(f"All repaired: {r['tx_hash']}")

    elif args.cmd == "jump":
        r = agent.space_jump()
        print(f"Jumped: {r['tx_hash']}")

    elif args.cmd == "tracking-jump":
        r = agent.tracking_jump(args.target)
        print(f"Tracking jump: {r['tx_hash']}")

    elif args.cmd == "move":
        r = agent.start_move(args.x, args.y, args.z)
        print(f"Moving: {r['tx_hash']}")

    elif args.cmd == "cancel-move":
        r = agent.cancel_move()
        print(f"Cancelled: {r['tx_hash']}")

    elif args.cmd == "claim-dft":
        r = agent.claim_daily_dft()
        print(f"DFT claimed: {r['tx_hash']}")

    elif args.cmd == "withdraw-fees":
        r = agent.withdraw_fees()
        print(f"Fees withdrawn: {r['tx_hash']}")

    elif args.cmd == "create-order":
        r = agent.create_order(args.energy, args.price)
        print(f"Order created: {r['tx_hash']}")

    elif args.cmd == "fill-order":
        r = agent.fill_order(args.order_id)
        print(f"Order filled: {r['tx_hash']}")

    elif args.cmd == "cancel-order":
        r = agent.cancel_order(args.order_id)
        print(f"Order cancelled: {r['tx_hash']}")

    elif args.cmd == "orders":
        orders = agent.get_active_orders()
        print(f"Active orders: {len(orders)}")
        for o in orders:
            print(f"  #{o[0]} seller={o[1][:10]}.. energy={o[2]} price={o[3]}")

    elif args.cmd == "approve":
        r = agent.token_approve(args.spender, args.amount)
        print(f"Approved: {r['tx_hash']}")

    # ── reads ──
    elif args.cmd in ("civ",):
        p = args.player or agent.address
        print_json(agent.get_civilization(p))

    elif args.cmd == "status":
        p = args.player or agent.address
        print_json(agent.status(p))

    elif args.cmd in ("statuses", "civs"):
        print_json(agent.statuses(args.players))

    elif args.cmd == "entry-fee":
        print(f"Entry fee: {agent.get_entry_fee()} wei")

    elif args.cmd == "battles":
        for r in agent.get_battle_history(limit=args.limit):
            winner = "W" if r["attackerWon"] else "L"
            print(f"  {r['timestamp']} {r['attacker'][:10]}→{r['defender'][:10]} "
                  f"dmg={r['damageDealt']} energy={r['stolenEnergy']} [{winner}]")

    elif args.cmd == "position":
        p = args.player or agent.address
        print_json(agent.get_position(p))

    elif args.cmd == "balance":
        p = args.player or agent.address
        print(f"DFT: {agent.token_balance(p) / 1e18:.4f}")

    elif args.cmd == "whoami":
        mode_map = {
            "signer": f"remote signer ({agent._signer_url})",
            "local": "local signing",
            "none": "read-only",
        }
        print(f"Account: {agent.address}")
        print(f"  Mode:  {mode_map.get(agent._signing_mode, agent._signing_mode)}")

    else:
        print(f"Unknown command: {args.cmd}", file=sys.stderr)
        sys.exit(1)


def _try_int(v: str):
    """Try to parse a string as int (for contract args that are numbers)."""
    try:
        return int(v)
    except (ValueError, TypeError):
        return v


# ══════════════════════════════════════════════════════════════════════════
# Keystore subcommands (unchanged from previous version)
# ══════════════════════════════════════════════════════════════════════════


def _add_keystore_sub(sub):
    ks = sub.add_parser("keystore", aliases=["ks"], help="Manage encrypted keystore")
    ksub = ks.add_subparsers(dest="ks_cmd", required=True)

    p = ksub.add_parser("init", help="Create a new keystore")
    p.add_argument("-f", "--file", default=None)

    p = ksub.add_parser("list", aliases=["ls"], help="List accounts")
    p.add_argument("-f", "--file", default=None)

    p = ksub.add_parser("add", help="Generate new key")
    p.add_argument("label", type=str)
    p.add_argument("-f", "--file", default=None)

    p = ksub.add_parser("import", help="Import existing key")
    p.add_argument("label", type=str)
    p.add_argument("private_key", type=str)
    p.add_argument("-f", "--file", default=None)

    p = ksub.add_parser("remove", aliases=["rm"], help="Remove account")
    p.add_argument("label", type=str)
    p.add_argument("-f", "--file", default=None)

    p = ksub.add_parser("export-addresses", aliases=["addresses", "addrs"],
                        help="Export address list (safe to share)")
    p.add_argument("-f", "--file", default=None)
    p.add_argument("-o", "--output", default=None)


def _handle_keystore(args):
    pw = os.environ.get("DF_KEYSTORE_PASS")

    if args.ks_cmd == "init":
        ks = keystore_init(args.file, pw)
        return

    ks = keystore_unlock(args.file, pw)

    if args.ks_cmd in ("list", "ls"):
        accounts = ks.list_accounts()
        if not accounts:
            print("  (empty keystore)")
            return
        print(f"  KeyStore: {ks.path}\n")
        print(f"  {'LABEL':<20}  ADDRESS")
        print(f"  {'─'*20}  {'─'*42}")
        for a in accounts:
            print(f"  {a['label']:<20}  {a['address']}")
        print(f"\n  ─── {len(accounts)} account(s) total ───")

    elif args.ks_cmd == "add":
        r = ks.add_account(args.label)
        print(f"✔ Added: {r['label']}  →  {r['address']}")

    elif args.ks_cmd == "import":
        r = ks.import_account(args.label, args.private_key)
        print(f"✔ Imported: {r['label']}  →  {r['address']}")

    elif args.ks_cmd in ("remove", "rm"):
        ks.remove_account(args.label)
        print(f"✔ Removed: {args.label}")

    elif args.ks_cmd in ("export-addresses", "addresses", "addrs"):
        accounts = ks.list_accounts()
        lines = [a["address"] for a in accounts]
        if args.output:
            with open(args.output, "w") as f:
                f.write("\n".join(lines) + "\n")
            print(f"✔ Exported {len(accounts)} address(es) to {args.output!r}")
        else:
            for a in accounts:
                print(f"  {a['address']}  ({a['label']})")


if __name__ == "__main__":
    main()
