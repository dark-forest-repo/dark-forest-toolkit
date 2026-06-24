#!/usr/bin/env python3
"""
Dark Forest 经济演化模拟器 (聚合模型)
=======================================
使用玩家群体分布代替单个玩家，大幅提升速度。
追踪所有守恒量，10年模拟 < 5秒。
"""

import math
from dataclasses import dataclass, field
from typing import List

# ══════════════════════════════════════
# 合约常量
# ══════════════════════════════════════

TOTAL_DFT = 4_206_900_000_000
DAILY_EMISSION = TOTAL_DFT // 3650  # 1,152,575,342

UPGRADE_COST_PARAMS = {
    'weapon': (10000, 8), 'shield': (7000, 6), 'radar': (8000, 7),
    'collector': (5000, 5), 'engine': (6000, 5),
}
ATTACK_E_BASE, ATTACK_E_PER_LV = 1000, 2000  # (simplified) attackCost = 1000 + atk*2; 合约实际公式
COLLECT_BASE, COLLECT_BONUS = 3, 10
DUR_BASE, DUR_PER_LV = 86400, 86400
REPAIR_COST = 1

# 能量市场
MARKET_FEE_BPS = 500  # 5% burn

def sqrt(x): return int(math.isqrt(x))
def up_cost(sys, lv):
    A, B = UPGRADE_COST_PARAMS[sys]
    return A * lv * (lv + B) // 100
def atk_cost(w): return ATTACK_E_BASE + ATTACK_E_PER_LV * w
def collect_rate(lv, ref=0):
    base = COLLECT_BASE if lv <= 1 else COLLECT_BASE + COLLECT_BONUS * sqrt(lv - 1)
    return int(base * (1000 + ref * 2) / 1000)
def max_dur(lv):
    return DUR_BASE if lv <= 1 else DUR_BASE + DUR_PER_LV * (lv - 1)
def jump_cost(jc):
    c = 5000 + 5000 * sqrt(min(jc + 1, 10000))
    return min(c, 150_000), min(3000 + 3000 * sqrt(min(jc + 1, 10000)), 100_000)


# ══════════════════════════════════════
# 玩家群体 (cohort)
# ══════════════════════════════════════

@dataclass
class Cohort:
    """代表一组行为相似的玩家"""
    count: int               # 人数
    style: str               # casual / active / pvper / whale
    lv_w: float = 1.0
    lv_s: float = 1.0
    lv_c: float = 1.0
    lv_r: float = 1.0
    lv_e: float = 1.0
    dft: float = 1000.0      # 人均 DFT
    energy: float = 2000.0   # 人均能量
    dur: float = DUR_BASE
    jc: int = 0
    churn_pct: float = 0.0   # 本日流失%
    
    @property
    def avg_lv(self):
        return (self.lv_w + self.lv_s + self.lv_c + self.lv_r + self.lv_e) / 5
    @property
    def is_maxed(self):
        return self.lv_w >= 100 and self.lv_s >= 100 and self.lv_c >= 100


@dataclass
class Sim:
    day: int = 0
    players: List[Cohort] = field(default_factory=list)
    
    # 守恒量
    dft_minted: float = 0.0
    dft_burned: float = 0.0
    dft_circulating: float = 0.0
    energy_produced: float = 0.0
    energy_consumed: float = 0.0
    market_volume: float = 0.0
    market_burned: float = 0.0
    battles: int = 0
    jumps: int = 0
    
    # 参数
    max_players = 10_000_000
    base_daily_new = 50
    growth_rate = 0.001
    base_churn = 0.003
    
    def run(self, years=10):
        for day in range(1, years * 365 + 1):
            self.day = day
            self.tick()
            if day % 365 == 0:
                self.report()
        self.summary()
    
    def tick(self):
        # 1. 新增玩家
        target = self.base_daily_new * (1 + self.growth_rate) ** (self.day / 365)
        target = min(target, self.max_players - self.total_count())
        new_n = max(0, int(target))
        if new_n > 0:
            styles = [('casual', 0.40), ('active', 0.35), ('pvper', 0.20), ('whale', 0.05)]
            for s, pct in styles:
                n = int(new_n * pct)
                if n > 0:
                    c = Cohort(count=n, style=s)
                    if s == 'whale':
                        c.dft = 1_000_000
                    self.players.append(c)
        
        # 2. 分发 DFT
        total = self.total_count()
        if total > 0:
            per = DAILY_EMISSION // total
            for c in self.players:
                c.dft += per * c.count
            self.dft_minted += per * total
        
        # 3. 玩家行为
        self.simulate_actions()
        
        # 4. 能量市场
        self.energy_market()
        
        # 5. 流失
        self.churn()
        
        # 6. 崩溃检测
        if self.detect_crash():
            return
    
    def total_count(self):
        return sum(c.count for c in self.players)
    
    def simulate_actions(self):
        for c in self.players:
            if c.count <= 0: continue
            n = c.count
            
            # 采集能量
            rate = collect_rate(int(c.lv_c))
            dur_available = min(86400, c.dur)
            if dur_available > 0:
                collected = dur_available * rate * n
                c.energy += collected / n
                c.dur -= dur_available
                self.energy_produced += collected
                # 修复
                if c.dur <= 0:
                    maxd = max_dur(int(c.lv_c))
                    repair = maxd * REPAIR_COST
                    if c.energy * n >= repair:
                        c.energy -= repair / n
                        c.dur = maxd
                        self.energy_consumed += repair
            
            # 按风格执行行为
            if c.style == 'casual':
                self._casual_day(c)
            elif c.style == 'active':
                self._active_day(c)
            elif c.style == 'pvper':
                self._pvp_day(c)
            elif c.style == 'whale':
                self._whale_day(c)
    
    def _upgrade(self, c: Cohort, system: str):
        """尝试升级一个系统"""
        lv_attr = f'lv_{system[0]}'
        lv = int(getattr(c, lv_attr))
        if lv >= 100: return
        cost = up_cost(system, lv)
        e_cost = cost // 2
        if c.dft * c.count >= cost and c.energy * c.count >= e_cost:
            c.dft -= cost / c.count
            c.energy -= e_cost / c.count
            setattr(c, lv_attr, lv + 1)
            self.dft_burned += cost
            self.energy_consumed += e_cost
    
    def _attack(self, c: Cohort, times: int):
        """执行多次攻击"""
        cost = atk_cost(int(c.lv_w))
        affordable = min(times, int(c.energy * c.count // cost))
        if affordable > 0:
            c.energy -= affordable * cost / c.count
            self.energy_consumed += affordable * cost
            self.battles += affordable
    
    def _jump(self, c: Cohort):
        """执行一次空间跳跃"""
        e, d = jump_cost(c.jc)
        if c.energy * c.count >= e and c.dft * c.count >= d:
            c.energy -= e / c.count
            c.dft -= d / c.count
            c.jc += 1
            self.energy_consumed += e
            self.dft_burned += d
            self.jumps += 1
    
    def _casual_day(self, c: Cohort):
        """轻度玩家"""
        self._upgrade(c, 'collector')  # 升最便宜的
        if c.lv_c >= 5: self._upgrade(c, 'shield')
        self._attack(c, random_int(0, 3))
    
    def _active_day(self, c: Cohort):
        """活跃玩家"""
        self._upgrade(c, 'weapon')
        if c.lv_w >= 10: self._upgrade(c, 'shield')
        self._attack(c, random_int(20, 50))
        if random_int(0, 9) < 2: self._jump(c)
    
    def _pvp_day(self, c: Cohort):
        """重度 PvPer"""
        self._upgrade(c, 'weapon')
        self._upgrade(c, 'shield')
        self._attack(c, random_int(200, 500))
        if random_int(0, 9) < 3: self._jump(c)
    
    def _whale_day(self, c: Cohort):
        """鲸鱼"""
        for sys in ['weapon', 'shield', 'collector', 'radar', 'engine']:
            for _ in range(3): self._upgrade(c, sys)
        self._attack(c, random_int(800, 1500))
        for _ in range(random_int(1, 5)): self._jump(c)
    
    def energy_market(self):
        """能量市场出清"""
        total_supply, total_demand = 0.0, 0.0
        for c in self.players:
            if c.count <= 0: continue
            surplus = max(0, c.energy - 30000)
            if surplus > 1000 and c.dft < 20000:
                total_supply += surplus * 0.3 * c.count
            elif c.energy < 15000 and c.dft > 5000:
                want = min(20000, c.dft * 0.2)
                total_demand += want * c.count
        
        traded = min(total_supply, total_demand)
        if traded > 0:
            burned = traded * MARKET_FEE_BPS // 10000
            self.market_volume += traded
            self.market_burned += burned
            self.energy_consumed += burned
    
    def churn(self):
        """玩家流失"""
        surviving = []
        for c in self.players:
            if c.count <= 0: continue
            # 流失率: 基础 + 满级惩罚 - 等级减免
            churn = self.base_churn
            if c.is_maxed: churn *= 2.0
            churn *= max(0.2, 1.0 - c.avg_lv / 200)
            if c.style == 'whale': churn *= 0.3
            if c.style == 'pvper': churn *= 0.5
            
            lost = int(c.count * churn)
            if lost > 0:
                c.count -= lost
            if c.count > 0:
                surviving.append(c)
        self.players = surviving
    
    def detect_crash(self) -> bool:
        if self.total_count() < 10 and self.day > 100:
            print(f"\n🔴 第{self.day}天崩溃: 鬼服 (仅剩{self.total_count()}人)")
            return True
        if self.day > 365 and self.dft_minted > 0:
            ratio = self.dft_burned / self.dft_minted
            if ratio < 0.005:
                print(f"\n🔴 第{self.day}天崩溃: 超通胀 (销毁/铸造={ratio:.2%})")
                return True
        return False
    
    def report(self):
        t = self.total_count()
        if t == 0: return
        avg_w = sum(c.lv_w * c.count for c in self.players) / t
        maxed = sum(c.count for c in self.players if c.is_maxed)
        burned_ratio = self.dft_burned / max(self.dft_minted, 1)
        pvp_day = self.battles / max(self.day, 1) / max(t, 1)
        
        print(f"\n第{self.day//365}年 (Day {self.day})")
        print(f"  玩家: {t:>8,} | 平均武器: {avg_w:>5.1f} | 满级: {maxed:>6,}")
        print(f"  铸造: {self.dft_minted:>14,.0f} | 销毁: {self.dft_burned:>14,.0f} | 销毁比: {burned_ratio:>6.1%}")
        print(f"  能量产出: {self.energy_produced:>14,.0f} | 消耗: {self.energy_consumed:>14,.0f}")
        print(f"  能量市场: {self.market_volume:>14,.0f} | 市场销毁: {self.market_burned:>14,.0f}")
        print(f"  PvP/人/天: {pvp_day:>6.2f} | 跳跃: {self.jumps:>8,}")
        
        if maxed > t * 0.5 and t > 1000:
            print(f"  ⚠️ {maxed/t:.0%}满级 — 长期目标缺失风险")
    
    def summary(self):
        t = self.total_count()
        print(f"\n{'='*55}")
        print(f"📊 {self.day}天模拟结束")
        print(f"{'='*55}")
        print(f"  最终玩家: {t:,}")
        print(f"  总铸造 DFT: {self.dft_minted:>14,.0f}")
        print(f"  总销毁 DFT: {self.dft_burned:>14,.0f}")
        print(f"  净增 DFT:   {self.dft_minted - self.dft_burned:>14,.0f}")
        print(f"  销毁/铸造:  {self.dft_burned/max(self.dft_minted,1):.1%}")
        print(f"  总能量产出: {self.energy_produced:>14,.0f}")
        print(f"  总能量消耗: {self.energy_consumed:>14,.0f}")
        print(f"  能量市场:   {self.market_volume:>14,.0f}")
        print(f"  市场销毁:   {self.market_burned:>14,.0f}")
        print(f"  总 PvP:     {self.battles:>12,}")
        print(f"  总跳跃:     {self.jumps:>12,}")


def random_int(lo, hi):
    """快速随机整数，不使用 random 模块，用简单线性同余"""
    global _seed
    _seed = (_seed * 1103515245 + 12345) & 0x7fffffff
    return lo + (_seed % (hi - lo + 1))
_seed = 42


if __name__ == '__main__':
    Sim().run(years=10)
