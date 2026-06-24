#!/usr/bin/env python3
"""
Dark Forest 经济演化模拟器
===========================
模拟 42069亿 DFT 总量下的 10 年经济演化。
追踪所有守恒量，识别崩溃模式。
"""

import random
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum

# ═══════════════════════════════════════════════════════
# 常量 (与合约完全一致)
# ═══════════════════════════════════════════════════════

TOTAL_DFT_SUPPLY  = 4_206_900_000_000
EMISSION_DAYS      = 3650
DAILY_DFT_EMISSION = TOTAL_DFT_SUPPLY // EMISSION_DAYS  # 1,152,575,342

# 升级成本: A × N × (N + B) / 100
UPGRADE_COST = {
    'weapon':    (1000, 8),
    'shield':    (700,  6),
    'radar':     (800,  7),
    'collector': (500,  5),
    'engine':    (600,  5),
}

# 攻击能量消耗: 200 + weaponLv × 250
ATTACK_ENERGY_BASE   = 1000
ATTACK_ENERGY_PER_LV = 2000

# 采集: 10 + 10 × sqrt(N-1)
COLLECT_BASE  = 3
COLLECT_BONUS = 10

# 耐久
DURABILITY_BASE     = 86400   # 1 天
DURABILITY_PER_LV   = 86400   # 每级 +1 天
REPAIR_COST_PER_SEC = 1

# 能量市场
ENERGY_MARKET_FEE_BPS = 500   # 5% 能量销毁

# 玩家初始
INITIAL_ENERGY = 2000
INITIAL_DFT    = 1000  # 新人入场赠送，或从 DEX 购买

# ═══════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════

def sqrt(x):
    """整数 sqrt"""
    return int(math.isqrt(x))

def upgrade_dft_cost(system: str, current_lv: int) -> int:
    """从 current_lv 升到 current_lv+1 的 DFT 成本"""
    A, B = UPGRADE_COST[system]
    return A * current_lv * (current_lv + B) // 100

def cumulative_upgrade_cost(system: str, target_lv: int) -> int:
    """从 Lv.1 升到 target_lv 的总 DFT 成本"""
    return sum(upgrade_dft_cost(system, lv) for lv in range(1, target_lv))

def attack_energy_cost(weapon_lv: int) -> int:
    return ATTACK_ENERGY_BASE + ATTACK_ENERGY_PER_LV * weapon_lv

def collect_rate(collector_lv: int, referrals: int = 0) -> int:
    """每秒能量采集速率"""
    if collector_lv <= 1:
        base = COLLECT_BASE
    else:
        base = COLLECT_BASE + COLLECT_BONUS * sqrt(collector_lv - 1)
    return int(base * (1000 + referrals * 2) / 1000)

def max_durability(collector_lv: int) -> int:
    """最大耐久（秒）"""
    if collector_lv <= 1:
        return DURABILITY_BASE
    return DURABILITY_BASE + DURABILITY_PER_LV * (collector_lv - 1)

def jump_energy_cost(jump_count: int) -> int:
    jc = min(jump_count + 1, 10000)
    cost = 5000 + 5000 * sqrt(jc)
    return min(cost, 150_000)

def jump_dft_cost(jump_count: int) -> int:
    jc = min(jump_count + 1, 10000)
    cost = 3000 + 3000 * sqrt(jc)
    return min(cost, 100_000)


# ═══════════════════════════════════════════════════════
# 玩家类型与行为
# ═══════════════════════════════════════════════════════

class PlayStyle(Enum):
    CASUAL     = "轻度"   # 每天上线领 DFT，偶尔升级
    ACTIVE     = "活跃"   # 每天 PvP 几场，认真升级
    PVP        = "重度"   # 高强度 PvP，大量消耗能量
    WHALE      = "鲸鱼"   # 大量买入 DFT，快速满级，主宰 PvP

@dataclass
class Player:
    id: int
    join_day: int
    
    # 等级
    weapon_lv: int = 1
    shield_lv: int = 1
    radar_lv: int = 1
    collector_lv: int = 1
    engine_lv: int = 1
    
    # 资源
    dft_balance: int = INITIAL_DFT
    energy: int = INITIAL_ENERGY
    
    # 耐久
    durability: int = DURABILITY_BASE
    last_collect_day: int = 0
    
    # 战斗
    jump_count: int = 0
    total_attacks: int = 0
    
    # 行为
    play_style: PlayStyle = PlayStyle.ACTIVE
    active_days: int = 0       # 实际上线天数
    churn_risk: float = 0.0    # 流失概率
    
    @property
    def total_level(self) -> int:
        return self.weapon_lv + self.shield_lv + self.radar_lv + self.collector_lv + self.engine_lv
    
    @property
    def is_maxed(self) -> bool:
        """是否 5 系统全满级"""
        return all(lv >= 100 for lv in [self.weapon_lv, self.shield_lv, self.radar_lv,
                                         self.collector_lv, self.engine_lv])
    
    def total_dft_invested(self) -> int:
        """累计投入的 DFT"""
        total = 0
        for sys in UPGRADE_COST:
            lv = getattr(self, f"{sys}_lv")
            total += cumulative_upgrade_cost(sys, lv)
        return total


# ═══════════════════════════════════════════════════════
# 全局模拟器
# ═══════════════════════════════════════════════════════

@dataclass
class SimState:
    day: int = 0
    total_dft_minted: int = 0
    total_dft_burned: int = 0
    total_dft_in_circulation: int = 0
    total_energy_produced: int = 0
    total_energy_consumed: int = 0
    total_energy_market_volume: int = 0
    total_energy_burned_market: int = 0
    total_dft_market_fees: int = 0
    total_battles: int = 0
    total_jumps: int = 0
    active_players: int = 0
    total_players_ever: int = 0
    players: List[Player] = field(default_factory=list)
    dft_price_estimate: float = 1.0  # 相对值，仅用于市场匹配
    
    # 崩溃检测
    crash_reasons: List[str] = field(default_factory=list)
    
    # 每日快照
    history: Dict = field(default_factory=lambda: {
        'day': [],
        'active_players': [],
        'dft_circulating': [],
        'dft_burned_cumulative': [],
        'energy_market_volume': [],
        'avg_weapon_lv': [],
        'pvp_per_player_per_day': [],
    })


class EconomySim:
    def __init__(self, seed: int = 42):
        random.seed(seed)
        self.state = SimState()
        
        # 参数配置
        self.max_sim_days = 3650  # 10 年
        self.daily_new_players_base = 50  # 基础新增
        self.player_growth_rate = 0.001   # 日增长率
        self.max_players = 10_000_000
        self.churn_base_rate = 0.005      # 基础日流失率
        
    def run(self):
        """运行完整模拟"""
        for day in range(1, self.max_sim_days + 1):
            self.state.day = day
            self._tick()
            
            if day % 365 == 0:
                self._snapshot(day)
                
            if len(self.state.crash_reasons) > 0:
                print(f"\n🔴 第 {day} 天: 经济崩溃!")
                for r in self.state.crash_reasons:
                    print(f"  原因: {r}")
                break
                
        self._print_final_summary()
    
    def _tick(self):
        """模拟一天"""
        s = self.state
        
        # 1. 新增玩家
        self._add_new_players()
        
        # 2. 玩家流失
        self._remove_churned_players()
        
        # 3. 分发 DFT
        self._distribute_dft()
        
        # 4. 活跃玩家执行日常行为
        self._simulate_player_actions()
        
        # 5. 能量市场
        self._run_energy_market()
        
        # 6. 检查崩溃条件
        self._check_crashes()
    
    def _add_new_players(self):
        s = self.state
        target = min(
            int(self.daily_new_players_base * (1 + self.player_growth_rate) ** (s.day / 365)),
            self.max_players - s.active_players
        )
        new_count = max(0, min(target, 5000))  # 单日上限避免暴增
        
        for _ in range(new_count):
            # 按比例分配玩家类型
            roll = random.random()
            if roll < 0.4:
                style = PlayStyle.CASUAL
            elif roll < 0.75:
                style = PlayStyle.ACTIVE
            elif roll < 0.95:
                style = PlayStyle.PVP
            else:
                style = PlayStyle.WHALE
            
            p = Player(
                id=s.total_players_ever,
                join_day=s.day,
                play_style=style,
            )
            # 鲸鱼玩家初始带大量 DFT
            if style == PlayStyle.WHALE:
                p.dft_balance = 1_000_000  # 从 DEX 买入
            
            s.players.append(p)
            s.total_players_ever += 1
            s.active_players += 1
    
    def _remove_churned_players(self):
        s = self.state
        remaining = []
        for p in s.players:
            # 流失概率随玩家等级升高而降低（沉没成本效应）
            base_churn = self.churn_base_rate
            level_factor = max(0.1, 1.0 - p.total_level / 500)
            churn = base_churn * level_factor
            
            # 鲸鱼/重度玩家流失率更低
            if p.play_style == PlayStyle.WHALE:
                churn *= 0.3
            elif p.play_style == PlayStyle.PVP:
                churn *= 0.5
            
            # 满级玩家流失率升高（目标缺失）
            if p.is_maxed:
                churn *= 2.0
            
            if random.random() > churn:
                remaining.append(p)
            else:
                s.active_players -= 1
                # 玩家离开时，其持有的 DFT 从活跃流通中移除（囤积/丢失）
                # 但不计入销毁——这些代币只是不再流通
        s.players = remaining
    
    def _distribute_dft(self):
        s = self.state
        if s.active_players == 0:
            return
        
        daily_per_player = DAILY_DFT_EMISSION // s.active_players
        total_minted = daily_per_player * s.active_players
        
        for p in s.players:
            p.dft_balance += daily_per_player
        
        s.total_dft_minted += total_minted
    
    def _simulate_player_actions(self):
        """每个活跃玩家执行一天的行为"""
        s = self.state
        for p in s.players:
            p.active_days += 1
            
            # 采集能量（受耐久限制）
            self._collect_energy(p)
            
            # 根据玩家类型执行行为
            if p.play_style == PlayStyle.CASUAL:
                self._casual_actions(p)
            elif p.play_style == PlayStyle.ACTIVE:
                self._active_actions(p)
            elif p.play_style == PlayStyle.PVP:
                self._pvp_actions(p)
            elif p.play_style == PlayStyle.WHALE:
                self._whale_actions(p)
    
    def _collect_energy(self, p: Player):
        """采集能量，消耗耐久"""
        # 简化：每天采集一次
        time_passed = 86400  # 1 天
        rate = collect_rate(p.collector_lv)
        
        if p.durability > 0:
            collect_time = min(time_passed, p.durability)
            collected = collect_time * rate
            p.energy += collected
            p.durability -= collect_time
            self.state.total_energy_produced += collected
            
            # 耐久耗尽后修复
            if p.durability <= 0:
                max_dur = max_durability(p.collector_lv)
                repair_cost = max_dur * REPAIR_COST_PER_SEC
                if p.energy >= repair_cost:
                    p.energy -= repair_cost
                    p.durability = max_dur
                    self.state.total_energy_consumed += repair_cost
    
    def _casual_actions(self, p: Player):
        """轻度玩家：每天升级一次最便宜的，偶尔 PvP"""
        # 升级最便宜的系统
        cheapest = min(UPGRADE_COST.keys(),
                       key=lambda s: upgrade_dft_cost(s, getattr(p, f"{s}_lv")))
        cost = upgrade_dft_cost(cheapest, getattr(p, f"{cheapest}_lv"))
        energy_cost = cost // 2
        
        if p.dft_balance >= cost and p.energy >= energy_cost:
            p.dft_balance -= cost
            p.energy -= energy_cost
            setattr(p, f"{cheapest}_lv", getattr(p, f"{cheapest}_lv") + 1)
            self.state.total_dft_burned += cost
            self.state.total_energy_consumed += energy_cost
        
        # 偶尔 PvP (20% 概率)
        if random.random() < 0.2:
            atk_cost = attack_energy_cost(p.weapon_lv)
            if p.energy >= atk_cost:
                p.energy -= atk_cost
                p.total_attacks += 1
                self.state.total_energy_consumed += atk_cost
                self.state.total_battles += 1
    
    def _active_actions(self, p: Player):
        """活跃玩家：每天多场 PvP，稳定升级"""
        # 优先升级武器
        cost = upgrade_dft_cost('weapon', p.weapon_lv)
        energy_cost = cost // 2
        
        if p.dft_balance >= cost and p.energy >= energy_cost and p.weapon_lv < 100:
            p.dft_balance -= cost
            p.energy -= energy_cost
            p.weapon_lv += 1
            self.state.total_dft_burned += cost
            self.state.total_energy_consumed += energy_cost
        
        # 每天 20-50 场 PvP
        pvp_count = random.randint(20, 50)
        for _ in range(pvp_count):
            atk_cost = attack_energy_cost(p.weapon_lv)
            if p.energy >= atk_cost:
                p.energy -= atk_cost
                p.total_attacks += 1
                self.state.total_energy_consumed += atk_cost
                self.state.total_battles += 1
    
    def _pvp_actions(self, p: Player):
        """重度 PvPer：大量战斗，跳跃追击，升级武器/护盾"""
        # 每天 200-500 场 PvP
        pvp_count = random.randint(200, 500)
        for _ in range(pvp_count):
            atk_cost = attack_energy_cost(p.weapon_lv)
            if p.energy >= atk_cost:
                p.energy -= atk_cost
                p.total_attacks += 1
                self.state.total_energy_consumed += atk_cost
                self.state.total_battles += 1
        
        # 升级武器到满
        if p.weapon_lv < 100:
            cost = upgrade_dft_cost('weapon', p.weapon_lv)
            energy_cost = cost // 2
            if p.dft_balance >= cost and p.energy >= energy_cost:
                p.dft_balance -= cost
                p.energy -= energy_cost
                p.weapon_lv += 1
                self.state.total_dft_burned += cost
                self.state.total_energy_consumed += energy_cost
        
        # 偶尔跳跃追击
        if random.random() < 0.1:
            jc = p.jump_count + 1
            e_cost = jump_energy_cost(jc)
            d_cost = jump_dft_cost(jc)
            if p.energy >= e_cost and p.dft_balance >= d_cost:
                p.energy -= e_cost
                p.dft_balance -= d_cost
                p.jump_count = jc
                self.state.total_energy_consumed += e_cost
                self.state.total_dft_burned += d_cost
                self.state.total_jumps += 1
    
    def _whale_actions(self, p: Player):
        """鲸鱼：快速满级，大量 PvP，大量跳跃"""
        # 快速升级所有系统到 100
        for sys in UPGRADE_COST:
            while getattr(p, f"{sys}_lv") < 100:
                cost = upgrade_dft_cost(sys, getattr(p, f"{sys}_lv"))
                energy_cost = cost // 2
                if p.dft_balance >= cost and p.energy >= energy_cost:
                    p.dft_balance -= cost
                    p.energy -= energy_cost
                    setattr(p, f"{sys}_lv", getattr(p, f"{sys}_lv") + 1)
                    self.state.total_dft_burned += cost
                    self.state.total_energy_consumed += energy_cost
                else:
                    break
        
        # 每天 1000+ 场 PvP
        pvp_count = random.randint(800, 1500)
        for _ in range(pvp_count):
            atk_cost = attack_energy_cost(p.weapon_lv)
            if p.energy >= atk_cost:
                p.energy -= atk_cost
                p.total_attacks += 1
                self.state.total_energy_consumed += atk_cost
                self.state.total_battles += 1
        
        # 大量跳跃
        for _ in range(random.randint(1, 5)):
            jc = p.jump_count + 1
            e_cost = jump_energy_cost(jc)
            d_cost = jump_dft_cost(jc)
            if p.energy >= e_cost and p.dft_balance >= d_cost:
                p.energy -= e_cost
                p.dft_balance -= d_cost
                p.jump_count = jc
                self.state.total_energy_consumed += e_cost
                self.state.total_dft_burned += d_cost
                self.state.total_jumps += 1
    
    def _run_energy_market(self):
        """
        能量市场：供需匹配，5% 能量销毁
        价格由供需关系决定
        """
        s = self.state
        if len(s.players) < 2:
            return
        
        # 计算每个玩家的能量盈余/赤字
        energy_supply = 0  # 可卖出的能量
        energy_demand = 0  # 想买入的能量
        dft_buy_power = 0  # 买家愿意支付的 DFT
        
        for p in s.players:
            # 如果能量超过阈值，视为可出售
            energy_surplus = max(0, p.energy - 50000)
            if energy_surplus > 1000 and p.dft_balance < 50000:
                # 缺 DFT 的玩家卖能量
                energy_supply += energy_surplus * 0.5  # 只卖一半
            elif p.energy < 10000 and p.dft_balance > 5000:
                # 需要能量的玩家买能量
                energy_demand += 30000
                dft_buy_power += p.dft_balance * 0.3  # 花 30% 的 DFT 买能量
        
        # 市场匹配
        if energy_supply > 0 and energy_demand > 0:
            traded = min(energy_supply, energy_demand)
            burned = traded * ENERGY_MARKET_FEE_BPS // 10000
            
            s.total_energy_market_volume += traded
            s.total_energy_burned_market += burned
            s.total_energy_consumed += burned  # 销毁也算消耗
            # 能量转移不计入总产出/消耗（这是玩家间转移，不是生产/销毁）
            # 但销毁部分计入消耗
    
    def _check_crashes(self):
        """检查各种经济崩溃条件"""
        s = self.state
        
        # 1. 鬼服: 活跃玩家 < 10
        if s.active_players < 10 and s.day > 100:
            s.crash_reasons.append(f"鬼服: 仅 {s.active_players} 名活跃玩家")
        
        # 2. 超级通胀: 每日销毁 < 每日铸造的 1%
        if s.day > 30:
            minted_30d = DAILY_DFT_EMISSION * 30
            # 粗略估算
            if s.total_dft_burned > 0 and s.total_dft_minted > 0:
                burn_ratio = s.total_dft_burned / s.total_dft_minted
                if burn_ratio < 0.01 and s.day > 365:
                    s.crash_reasons.append(
                        f"超通胀: 销毁/铸造比 {burn_ratio:.1%} < 1%"
                    )
        
        # 3. 玩家停滞: 平均等级长期不增长
        if s.day > 365 and len(s.players) > 10:
            avg_lv = sum(p.weapon_lv for p in s.players) / len(s.players)
            if avg_lv < 2 and s.day > 1000:
                s.crash_reasons.append(f"停滞: 平均武器等级 {avg_lv:.1f}")
        
        # 4. 能量崩溃: 无人生产/消耗能量
        if s.day > 100 and s.total_energy_produced == 0:
            s.crash_reasons.append("能量崩溃: 零产出")
        
        # 5. 鲸鱼垄断: 单一玩家持有 > 50% 的流通 DFT
        if len(s.players) > 10:
            total_dft = sum(p.dft_balance for p in s.players)
            if total_dft > 0:
                max_share = max(p.dft_balance for p in s.players) / total_dft
                if max_share > 0.5:
                    s.crash_reasons.append(f"鲸鱼垄断: 最大持仓 {max_share:.1%}")
        
        # 6. DFT 总流通异常: 高于理论上限
        theoretical_max = TOTAL_DFT_SUPPLY + s.total_dft_minted
        if s.total_dft_burned > theoretical_max:
            s.crash_reasons.append("守恒错误: 销毁超过总供应")
    
    def _snapshot(self, day):
        """记录快照"""
        s = self.state
        if len(s.players) == 0:
            return
        
        avg_weapon = sum(p.weapon_lv for p in s.players) / len(s.players)
        pvp_total = sum(p.total_attacks for p in s.players)
        pvp_pppd = pvp_total / max(len(s.players), 1) / max(day, 1)
        total_dft = sum(p.dft_balance for p in s.players)
        
        s.history['day'].append(day)
        s.history['active_players'].append(s.active_players)
        s.history['dft_circulating'].append(total_dft)
        s.history['dft_burned_cumulative'].append(s.total_dft_burned)
        s.history['energy_market_volume'].append(s.total_energy_market_volume)
        s.history['avg_weapon_lv'].append(avg_weapon)
        s.history['pvp_per_player_per_day'].append(pvp_pppd)
        
        # 打印年度报告
        maxed = sum(1 for p in s.players if p.is_maxed)
        total_dft_in_system = total_dft + s.total_dft_burned
        print(f"\n{'='*60}")
        print(f"第 {day//365} 年 (第 {day} 天)")
        print(f"{'='*60}")
        print(f"  活跃玩家:        {s.active_players:>8,}")
        print(f"  总玩家(累计):    {s.total_players_ever:>8,}")
        print(f"  平均武器等级:    {avg_weapon:>8.1f}")
        print(f"  满级玩家:        {maxed:>8,}")
        print(f"  流通 DFT:        {total_dft:>16,}")
        print(f"  累计销毁 DFT:    {s.total_dft_burned:>16,}")
        print(f"  销毁/铸造比:     {s.total_dft_burned/max(s.total_dft_minted,1):>8.1%}")
        print(f"  能量市场(累计):  {s.total_energy_market_volume:>16,}")
        print(f"  能量市场销毁:    {s.total_energy_burned_market:>16,}")
        print(f"  PvP 总场次:      {s.total_battles:>12,}")
        print(f"  总跳跃:          {s.total_jumps:>12,}")
        
        # 检查异常
        if maxed > s.active_players * 0.5 and s.active_players > 100:
            print(f"  ⚠️   {maxed/s.active_players:.0%} 玩家已满级 — 可能缺乏长期目标")
        if s.total_dft_burned / max(s.total_dft_minted, 1) < 0.05:
            print(f"  ⚠️  低销毁率 — 通胀压力大")
    
    def _print_final_summary(self):
        s = self.state
        print(f"\n{'='*60}")
        print("📊 模拟总结")
        print(f"{'='*60}")
        print(f"  运行天数:        {s.day:,}")
        print(f"  最终活跃玩家:    {s.active_players:,}")
        print(f"  总玩家(累计):    {s.total_players_ever:,}")
        
        if len(s.players) > 0:
            avg_w = sum(p.weapon_lv for p in s.players) / len(s.players)
            print(f"  平均武器等级:    {avg_w:.1f}")
        
        print(f"  总铸造 DFT:      {s.total_dft_minted:>16,}")
        print(f"  总销毁 DFT:      {s.total_dft_burned:>16,}")
        print(f"  净增 DFT:        {s.total_dft_minted - s.total_dft_burned:>16,}")
        print(f"  销毁/铸造比:     {s.total_dft_burned/max(s.total_dft_minted,1):.1%}")
        print(f"  总能量产出:      {s.total_energy_produced:>16,}")
        print(f"  总能量消耗:      {s.total_energy_consumed:>16,}")
        print(f"  能量市场交易:    {s.total_energy_market_volume:>16,}")
        print(f"  市场销毁能量:    {s.total_energy_burned_market:>16,}")
        print(f"  总 PvP 场次:     {s.total_battles:>12,}")
        print(f"  总空间跳跃:      {s.total_jumps:>12,}")
        
        if s.crash_reasons:
            print(f"\n🔴 崩溃原因:")
            for r in s.crash_reasons:
                print(f"  • {r}")
        else:
            print(f"\n✅ 经济未崩溃 (运行 {s.day} 天)")


# ═══════════════════════════════════════════════════════
# 运行
# ═══════════════════════════════════════════════════════

if __name__ == '__main__':
    sim = EconomySim(seed=42)
    sim.run()
