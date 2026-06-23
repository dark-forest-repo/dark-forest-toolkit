"""Dark Forest Python Agent — thin client for all game interactions.

Architecture
═════════════
    Agent 只管两件事：
      1. execute()  — 编码 ABI 调用 → 发给 signer（或本地签名）
      2. read()     — eth_call 读取链上状态

    签名逻辑全在 signer 里（见 ``signer_server.py``），agent 不接触私钥。
    密钥管理全在 keystore 里（见 ``keystore.py``），agent 不管理账户。

Usage
═══════
    agent = DarkForestAgent(
        rpc_url="https://bsc-dataseed.binance.org",
        signer_url="http://localhost:43567",
        signer_token="xxx",
        proxy="0x...", token="0x...", market="0x...", alliance="0x...",
    )

    # 通用接口
    receipt = agent.execute("game", "createCivilization", ["MyCiv"], value=1e17)
    result  = agent.read("game", "getCivilization", ["0x..."])

    # 也保留了旧方法名作为兼容
    receipt = agent.create_civilization("MyCiv")
    data    = agent.get_civilization("0x...")
"""

import json
import os
from urllib.request import Request, urlopen
from urllib.error import URLError

from web3 import Web3
from web3.middleware import geth_poa_middleware

from .abi import DARK_FOREST_ABI, DFT_ABI, MARKET_ABI, ALLIANCE_ABI

SYSTEM_NAMES = {0: "collector", 1: "weapon", 2: "shield", 3: "radar", 4: "engine"}

# Contract name → ABI mapping
_CONTRACT_ABIS: dict[str, list] = {
    "game":    DARK_FOREST_ABI,
    "proxy":   DARK_FOREST_ABI,
    "token":   DFT_ABI,
    "dft":     DFT_ABI,
    "market":  MARKET_ABI,
    "energy":  MARKET_ABI,
    "alliance": ALLIANCE_ABI,
}


class DarkForestAgent:
    """Thin agent — execute() writes, read() queries, no signing logic."""

    def __init__(
        self,
        rpc_url: str,
        # ── signing mode (remote signer recommended) ──
        signer_url: str | None = None,
        signer_token: str | None = None,
        # ── legacy: local signing (insecure on cloud) ──
        private_key: str | None = None,
        account: str | None = None,
        keystore_path: str | None = None,
        keystore_password: str | None = None,
        # ── contract addresses ──
        proxy: str | None = None,
        token: str | None = None,
        market: str | None = None,
        alliance: str | None = None,
        # ── aliases (backward compat) ──
        proxy_addr: str | None = None,
        token_addr: str | None = None,
        market_addr: str | None = None,
        alliance_addr: str | None = None,
    ):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to {rpc_url}")

        # ── resolve signing mode ──
        self._signer_url: str | None = None
        self._signer_token: str | None = None
        self._local_account = None
        self._signing_mode: str = "none"  # "signer" | "local" | "none"
        self.address: str = "0x0000000000000000000000000000000000000000"

        # Priority: signer > private_key > account(keystore)
        self._signer_url = signer_url or os.environ.get("DF_SIGNER_URL")
        self._signer_token = signer_token or os.environ.get("DF_SIGNER_TOKEN", "")

        if self._signer_url:
            self._signing_mode = "signer"
            self.address = self._signer_get("/address")["address"]

        elif private_key:
            self._local_account = self.w3.eth.account.from_key(private_key)
            self.address = self._local_account.address
            self._signing_mode = "local"

        elif account:
            from .keystore import KeyStore
            ks = KeyStore(keystore_path)
            ks.unlock(keystore_password or os.environ.get("DF_KEYSTORE_PASS"))
            self._local_account = self.w3.eth.account.from_key(ks.get_private_key(account))
            self.address = ks.get_address(account)
            self._signing_mode = "local"

        # ── resolve contract addresses ──
        self._addrs: dict[str, str] = {}
        for name, env_key, fallback in [
            ("game",    "PROXY_ADDR",    proxy or proxy_addr or ""),
            ("proxy",   "PROXY_ADDR",    proxy or proxy_addr or ""),
            ("token",   "TOKEN_ADDR",    token or token_addr or ""),
            ("dft",     "TOKEN_ADDR",    token or token_addr or ""),
            ("market",  "MARKET_ADDR",   market or market_addr or ""),
            ("energy",  "MARKET_ADDR",   market or market_addr or ""),
            ("alliance","ALLIANCE_ADDR", alliance or alliance_addr or ""),
        ]:
            addr = os.getenv(env_key, fallback)
            if addr:
                self._addrs[name] = Web3.to_checksum_address(addr)

        # ── cached web3 contract instances ──
        self._contracts: dict[str, object] = {}
        for name, addr in self._addrs.items():
            abi = _CONTRACT_ABIS.get(name)
            if abi:
                self._contracts[name] = self.w3.eth.contract(address=addr, abi=abi)

        # Gas config (only used in local mode)
        self.gas_limit = 2_000_000
        self.gas_multiplier = 1.1

    # ══════════════════════════════════════════════
    # Core API — 2 methods
    # ══════════════════════════════════════════════

    def execute(self, contract: str, func: str, args: list | None = None,
                value: int = 0) -> dict:
        """Execute a write transaction.

        Encodes the function call via ABI and sends it to the signer
        (or signs locally). Returns the receipt dict.

        Args:
            contract:  ``"game"``, ``"proxy"``, ``"token"``, ``"dft"``,
                       ``"market"``, ``"energy"``, ``"alliance"``
            func:      Function name, e.g. ``"createCivilization"``
            args:      List of positional arguments
            value:     ``msg.value`` in wei (default 0)

        Returns:
            Receipt dict with ``tx_hash``, ``block_number``, ``status``.
        """
        c = self._contracts.get(contract)
        if not c:
            raise ValueError(f"Unknown contract '{contract}'. Available: {list(self._contracts.keys())}")

        args = args or []
        data = c.encodeABI(fn_name=func, args=args)

        if self._signing_mode == "signer":
            return self._signer_post("/sign-and-send", {
                "to": c.address,
                "data": data,
                "value": hex(value),
            })
        elif self._signing_mode == "local":
            tx = c.functions[func](*args).build_transaction({
                "from": self.address,
                "nonce": self.w3.eth.get_transaction_count(self.address),
                "gas": self.gas_limit,
                "gasPrice": int(self.w3.eth.gas_price * self.gas_multiplier),
                "value": value,
            })
            signed = self._local_account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            if receipt["status"] != 1:
                raise RuntimeError(f"Transaction failed: {tx_hash.hex()}")
            return {
                "tx_hash": tx_hash.hex(),
                "block_number": receipt["blockNumber"],
                "status": receipt["status"],
                "gas_used": receipt["gasUsed"],
            }
        else:
            raise RuntimeError(
                "No signing method configured. "
                "Set DF_SIGNER_URL (+ token) or pass private_key / account."
            )

    def read(self, contract: str, func: str, args: list | None = None):
        """Call a read-only function (eth_call).

        Args:
            contract:  Contract name (same as execute)
            func:      Function name
            args:      List of positional arguments

        Returns:
            Raw return value from the contract (tuple, list, or scalar).
        """
        c = self._contracts.get(contract)
        if not c:
            raise ValueError(f"Unknown contract '{contract}'. Available: {list(self._contracts.keys())}")
        args = args or []
        fn = getattr(c.functions, func)
        return fn(*args).call()

    # ══════════════════════════════════════════════
    # Signer HTTP helpers
    # ══════════════════════════════════════════════

    def _signer_get(self, path: str) -> dict:
        url = self._signer_url.rstrip("/") + path
        headers = {"Authorization": f"Bearer {self._signer_token}"} if self._signer_token else {}
        req = Request(url, headers=headers)
        try:
            resp = urlopen(req, timeout=30)
            result = json.loads(resp.read().decode())
            if "error" in result:
                raise RuntimeError(f"Signer error: {result['error']}")
            return result
        except URLError as e:
            raise RuntimeError(f"Signer not reachable at {url}: {e}")

    def _signer_post(self, path: str, body: dict) -> dict:
        url = self._signer_url.rstrip("/") + path
        data = json.dumps(body).encode()
        headers = {"Content-Type": "application/json"}
        if self._signer_token:
            headers["Authorization"] = f"Bearer {self._signer_token}"
        req = Request(url, data=data, headers=headers)
        try:
            resp = urlopen(req, timeout=120)
            result = json.loads(resp.read().decode())
            if "error" in result:
                raise RuntimeError(f"Signer error: {result['error']}")
            return result
        except URLError as e:
            raise RuntimeError(f"Signer not reachable at {url}: {e}")

    # ══════════════════════════════════════════════
    # Backward-compat wrappers（旧方法名，内部调 execute/read）
    # ══════════════════════════════════════════════

    # ── civ ──
    def create_civilization(self, name: str, referrer: str = None, value_wei: int = None):
        if value_wei is None:
            fee = self.read("game", "getEntryFee")
            value_wei = fee * 101 // 100
        args = [name, referrer] if referrer else [name]
        return self.execute("game", "createCivilization", args, value=value_wei)

    def rebuild_civilization(self):
        return self.execute("game", "rebuildCivilization")

    # ── upgrade ──
    def upgrade_system(self, sys_id: int):
        assert 0 <= sys_id <= 4
        return self.execute("game", "upgradeSystem", [sys_id])

    def upgrade(self, system: str):
        m = {"collector": 0, "weapon": 1, "shield": 2, "radar": 3, "engine": 4}
        return self.upgrade_system(m[system])

    # ── energy ──
    def collect_energy(self):
        return self.execute("game", "collectEnergy")

    def repair_collector(self, amount: int):
        return self.execute("game", "repairCollector", [amount])

    def repair_all(self):
        return self.execute("game", "repairAll")

    def approve_energy(self, spender: str, amount: int):
        return self.execute("game", "approveEnergy", [spender, amount])

    # ── combat ──
    def attack(self, target: str):
        return self.execute("game", "attack", [target])

    def repair_shield(self, amount: int):
        return self.execute("game", "repairShield", [amount])

    def assist_shield_repair(self, target: str, amount: int):
        return self.execute("game", "assistShieldRepair", [target, amount])

    def regen_shield(self):
        return self.execute("game", "regenShield")

    def claim_combat_energy(self):
        return self.execute("game", "claimCombatEnergy")

    # ── movement ──
    def space_jump(self):
        return self.execute("game", "spaceJump")

    def tracking_jump(self, target: str):
        return self.execute("game", "trackingJump", [target])

    def start_move(self, x: int, y: int, z: int):
        return self.execute("game", "startMove", [x, y, z])

    def cancel_move(self):
        return self.execute("game", "cancelMove")

    # ── dft ──
    def claim_daily_dft(self):
        return self.execute("game", "claimDailyDFT")

    def withdraw_fees(self):
        return self.execute("game", "withdrawFees")

    # ── market ──
    def create_order(self, energy: int, price: int):
        return self.execute("market", "createOrder", [energy, price])

    def fill_order(self, order_id: int):
        return self.execute("market", "fillOrder", [order_id])

    def cancel_order(self, order_id: int):
        return self.execute("market", "cancelOrder", [order_id])

    def withdraw_dft_fees(self):
        return self.execute("market", "withdrawDftFees")

    # ── alliance ──
    def create_alliance(self, name: str):
        return self.execute("alliance", "createAlliance", [name])

    def join_alliance(self, id_bytes32: bytes):
        return self.execute("alliance", "joinAlliance", [id_bytes32])

    def leave_alliance(self, id_bytes32: bytes):
        return self.execute("alliance", "leaveAlliance", [id_bytes32])

    def kick_member(self, id_bytes32: bytes, member: str):
        return self.execute("alliance", "kickMember", [id_bytes32, member])

    def disband_alliance(self, id_bytes32: bytes):
        return self.execute("alliance", "disbandAlliance", [id_bytes32])

    # ── token ──
    def token_balance(self, who: str = None) -> int:
        return self.read("token", "balanceOf", [who or self.address])

    def token_approve(self, spender: str, amount: int):
        return self.execute("token", "approve", [spender, amount])

    def token_total_supply(self) -> int:
        return self.read("token", "totalSupply")

    # ── views ──
    def get_entry_fee(self) -> int:
        return self.read("game", "getEntryFee")

    def get_civilization(self, player: str | None = None):
        raw = self.read("game", "getCivilization", [player or self.address])
        return {
            "name": raw[0], "location": {"x": raw[1][0], "y": raw[1][1], "z": raw[1][2]},
            "energy": raw[2], "health": raw[3],
            "energyCollectorLv": raw[4], "weaponLv": raw[5], "radarLv": raw[6],
            "shieldLv": raw[7], "engineLv": raw[8], "scanRange": raw[9],
            "lastUpdateTime": raw[10], "exists": raw[11], "isRuins": raw[12],
            "ruinsTimestamp": raw[13],
        }

    def get_civilizations(self, players: list[str]) -> list[dict]:
        raw_list = self.read("game", "getCivilizations", [players])
        return [{
            "name": r[0], "location": {"x": r[1][0], "y": r[1][1], "z": r[1][2]},
            "energy": r[2], "health": r[3],
            "energyCollectorLv": r[4], "weaponLv": r[5], "radarLv": r[6],
            "shieldLv": r[7], "engineLv": r[8], "scanRange": r[9],
            "lastUpdateTime": r[10], "exists": r[11], "isRuins": r[12],
            "ruinsTimestamp": r[13],
        } for r in raw_list]

    def get_simple_statuses(self, players: list[str]) -> list[dict]:
        raw_list = self.read("game", "getSimpleStatuses", [players])
        return [{
            "player": r[0], "energy": r[1], "health": r[2],
            "collectorLv": r[3], "weaponLv": r[4], "shieldLv": r[5],
            "radarLv": r[6], "engineLv": r[7], "shieldHP": r[8],
            "shieldMax": r[9], "exists": r[10], "isRuins": r[11],
        } for r in raw_list]

    def get_positions(self, players: list[str]) -> list[dict]:
        raw_pos, raw_moving, raw_eta = self.read("game", "getPositions", [players])
        return [{
            "player": players[i],
            "position": {"x": raw_pos[i][0], "y": raw_pos[i][1], "z": raw_pos[i][2]},
            "isMoving": raw_moving[i], "etaSeconds": raw_eta[i],
        } for i in range(len(players))]

    def get_shield_hp(self, player: str | None = None):
        p = player or self.address
        return {"current": self.read("game", "getCurrentShieldHP", [p]),
                "max": self.read("game", "getMaxShieldHP", [p])}

    def get_attack_info(self, player: str | None = None):
        p = player or self.address
        tokens, mx, interval, rate = self.read("game", "getAttackTokenInfo", [p])
        return {"power": self.read("game", "getAttackPower", [p]),
                "energyCost": self.read("game", "getAttackEnergyCost", [p]),
                "tokens": tokens, "maxTokens": mx,
                "intervalSec": interval, "attacksPerSec": rate}

    def get_collect_info(self, player: str | None = None):
        p = player or self.address
        cur, mx = self.read("game", "getCollectorDurability", [p])
        return {"rate": self.read("game", "getEnergyCollectRate", [p]),
                "durability": cur, "maxDurability": mx}

    def get_upgrade_cost(self, player: str | None = None, system: str = ""):
        p = player or self.address
        dft, energy = self.read("game", "getUpgradeCost", [p, system])
        return {"dft": dft, "energy": energy}

    def get_battle_history(self, offset=0, limit=10) -> list:
        records = self.read("game", "getBattleHistory", [offset, limit])
        return [{"attacker": r[0], "defender": r[1], "timestamp": r[2],
                 "damageDealt": r[3], "shieldDamage": r[4], "healthDamage": r[5],
                 "stolenEnergy": r[6], "downgradedSystem": r[7], "attackerWon": r[8]}
                for r in records]

    def get_battle_count(self) -> int:
        return self.read("game", "getBattleCount")

    def get_player_count(self) -> int:
        return self.read("game", "getPlayerCount")

    def get_jump_count(self, player: str | None = None) -> int:
        return self.read("game", "getJumpCount", [player or self.address])

    def get_position(self, player: str | None = None):
        p = player or self.address
        pos, moving, eta = self.read("game", "getCurrentPosition", [p])
        return {"position": {"x": pos[0], "y": pos[1], "z": pos[2]},
                "isMoving": moving, "etaSeconds": eta}

    def is_in_range(self, scanner: str, target: str) -> bool:
        return self.read("game", "isInRange", [scanner, target])

    def get_distance(self, a: str, b: str) -> int:
        return self.read("game", "getDistance", [a, b])

    def get_total_civs(self) -> int:
        return self.read("game", "totalCivilizations")

    def get_active_civs(self) -> int:
        return self.read("game", "activeCivilizationCount")

    def get_owner(self) -> str:
        return self.read("game", "owner")

    def get_pending_combat_energy(self, player: str | None = None) -> int:
        return self.read("game", "pendingCombatEnergy", [player or self.address])

    def get_order_count(self) -> int:
        return self.read("market", "getOrderCount")

    def get_player_alliance(self, player: str) -> bytes:
        return self.read("alliance", "playerAlliance", [player])

    # ── convenience ──
    def status(self, player: str | None = None) -> dict:
        p = player or self.address
        civ = self.get_civilization(p)
        shield = self.get_shield_hp(p)
        attack = self.get_attack_info(p)
        collect = self.get_collect_info(p)
        return {
            "name": civ["name"], "exists": civ["exists"], "isRuins": civ["isRuins"],
            "energy": civ["energy"], "health": civ["health"],
            "shieldHP": shield["current"], "shieldMax": shield["max"],
            "levels": {"collector": civ["energyCollectorLv"], "weapon": civ["weaponLv"],
                       "shield": civ["shieldLv"], "radar": civ["radarLv"], "engine": civ["engineLv"]},
            "attackPower": attack["power"], "attackCost": attack["energyCost"],
            "attackTokens": attack["tokens"], "collectRate": collect["rate"],
            "collectorDurability": collect["durability"],
            "jumpCount": self.get_jump_count(p),
            "pendingCombatEnergy": self.get_pending_combat_energy(p),
            "dftBalance": self.token_balance(p) if "token" in self._contracts else 0,
            "totalCivs": self.get_total_civs(), "activeCivs": self.get_active_civs(),
            "battleCount": self.get_battle_count(), "entryFee": self.get_entry_fee(),
        }

    def statuses(self, players: list[str]) -> list[dict]:
        status_list = self.get_simple_statuses(players)
        pos_list = self.get_positions(players)
        pos_by = {p["player"]: p for p in pos_list}
        return [{
            "player": s["player"], "exists": s["exists"], "isRuins": s["isRuins"],
            "energy": s["energy"], "health": s["health"],
            "levels": {"collector": s["collectorLv"], "weapon": s["weaponLv"],
                       "shield": s["shieldLv"], "radar": s["radarLv"], "engine": s["engineLv"]},
            "shieldHP": s["shieldHP"], "shieldMax": s["shieldMax"],
            "position": pos_by.get(s["player"], {}).get("position"),
            "isMoving": pos_by.get(s["player"], {}).get("isMoving"),
            "etaSeconds": pos_by.get(s["player"], {}).get("etaSeconds"),
        } for s in status_list]
