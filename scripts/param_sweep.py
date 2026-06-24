#!/usr/bin/env python3
"""
Dark Forest 参数扫描 — 寻找最优经济参数

目标：在 10 年周期内，创造出健康的 DFT 稀缺性和合理的玩家进度。

指标：
  ✅ 销毁率 > 40%（升级消耗占大部分铸造量）
  ✅ 平均武器等级 10-30（10 年后既不太离谱也不太菜）
  ✅ 供需比 > 1.5x（需求超过供给）
  ✅ 满级玩家 < 10%（避免"满级即弃坑"）
  ✅ 通胀率 < 20%

扫描维度：
  - 升级成本倍率: 1x, 3x, 5x, 10x, 20x
  - 日释放倍率: 1x, 0.5x, 0.2x, 0.1x
  - 攻击能量倍率: 1x, 3x, 5x
"""

import sys, os, copy, math
sys.path.insert(0, os.path.dirname(__file__))

import dark_forest_econ_sim as sim_mod
from dark_forest_econ_sim import Sim, Cohort, TOTAL_DFT


# 参数扫描范围
UPGRADE_MULTIPLIERS = [1, 3, 5, 8, 12, 20]
EMISSION_MULTIPLIERS = [1.0, 0.5, 0.3, 0.15, 0.08]
SCENARIO = {
    "initial": 30000,
    "growth": 0.005,
    "max_players": 200000,
    "years": 5,
}

STYLE_DIST = [
    ("farmer",  0.40, 0.002),
    ("fighter", 0.35, 0.005),
    ("whale",   0.15, 0.001),
    ("flipper", 0.10, 0.01),
]

# 存储原始值
ORIG = {}


def backup_constants():
    for k in ['UPGRADE_COST_PARAMS', 'DAILY_EMISSION', 'ATTACK_E_BASE',
              'ATTACK_E_PER_LV', 'COLLECT_BASE', 'COLLECT_BONUS']:
        ORIG[k] = copy.deepcopy(getattr(sim_mod, k))


def apply_multipliers(upgrade_mul, emission_mul, attack_mul):
    """修改模拟常量"""
    sim_mod.DAILY_EMISSION = int(ORIG['DAILY_EMISSION'] * emission_mul)
    
    # 升级成本：乘以倍率
    new_params = {}
    for sys, (A, B) in ORIG['UPGRADE_COST_PARAMS'].items():
        new_params[sys] = (int(A * upgrade_mul), B)
    sim_mod.UPGRADE_COST_PARAMS = new_params
    
    # 攻击能量消耗
    sim_mod.ATTACK_E_BASE = int(ORIG['ATTACK_E_BASE'] * attack_mul)
    sim_mod.ATTACK_E_PER_LV = int(ORIG['ATTACK_E_PER_LV'] * attack_mul)


def restore_constants():
    for k, v in ORIG.items():
        setattr(sim_mod, k, copy.deepcopy(v))


def run_sim(years=5) -> dict:
    """运行一次模拟，返回关键指标"""
    n = SCENARIO["initial"]
    sim = Sim(players=[
        Cohort(count=int(n * pct), style=style, churn_pct=churn)
        for style, pct, churn in STYLE_DIST
    ])
    sim.growth_rate = SCENARIO["growth"]
    sim.max_players = SCENARIO["max_players"]
    sim.run(years=years)
    
    t = sim.total_count() or 1
    burned = sim.dft_burned
    minted = sim.dft_minted or 1
    maxed = sum(c.count for c in sim.players if c.is_maxed)
    
    avg_weapon = sum(c.lv_w * c.count for c in sim.players) / t
    
    return {
        "days": sim.day,
        "players": t,
        "minted": minted,
        "burned": burned,
        "burn_pct": burned / minted * 100,
        "avg_weapon": avg_weapon,
        "maxed_pct": maxed / t * 100,
        "battles": sim.battles,
        "jumps": sim.jumps,
    }


def score(result: dict) -> float:
    """对模拟结果打分（0-100），越高越好"""
    s = 0.0
    bp = result["burn_pct"]
    aw = result["avg_weapon"]
    mp = result["maxed_pct"]
    
    # 销毁率：理想 40-70%
    if 40 <= bp <= 70:
        s += 40
    elif 20 <= bp < 40:
        s += 25 + (bp - 20) / 20 * 15
    elif 70 < bp <= 90:
        s += 25
    elif 10 <= bp < 20:
        s += 10
    else:
        s += bp / 10 * 5
    
    # 平均武器等级：理想 10-30
    if 10 <= aw <= 30:
        s += 30
    elif 30 < aw <= 50:
        s += 20 - (aw - 30) / 20 * 10
    elif 5 <= aw < 10:
        s += 15 + (aw - 5) / 5 * 10
    else:
        s += aw / 5 * 5
    
    # 满级比例：越低越好
    if mp < 5:
        s += 20
    elif mp < 15:
        s += 15 - (mp - 5) / 10 * 5
    elif mp < 30:
        s += 8
    else:
        s += max(0, 8 - (mp - 30) / 70 * 8)
    
    # 玩家数惩罚（鬼服）
    if result["players"] < 100:
        s = 0
    elif result["players"] < 1000:
        s *= 0.5
    
    return s


def main():
    backup_constants()
    
    print("=" * 90)
    print("🔬  Dark Forest 参数扫描")
    print("=" * 90)
    print(f"  初始玩家: {SCENARIO['initial']:,} | 日增长: {SCENARIO['growth']:.1%}")
    print(f"  模拟年限: {SCENARIO['years']} 年")
    print()
    print(f"  扫描维度:")
    print(f"    升级倍率: {UPGRADE_MULTIPLIERS}")
    print(f"    日释放倍率: {EMISSION_MULTIPLIERS}")
    print(f"    攻击能量倍率: 1x")
    print(f"  共计: {len(UPGRADE_MULTIPLIERS) * len(EMISSION_MULTIPLIERS)} 组")
    print()
    print(f"  {'升级倍率':>8} {'日释放':>8} {'销毁率':>8} {'武器Lv':>7} {'满级%':>6} {'玩家':>8} {'总分':>6}")
    print(f"  {'-' * 8} {'-' * 8} {'-' * 8} {'-' * 7} {'-' * 6} {'-' * 8} {'-' * 6}")
    
    results = []
    
    for um in UPGRADE_MULTIPLIERS:
        for em in EMISSION_MULTIPLIERS:
            try:
                apply_multipliers(um, em, attack_mul=1)
                r = run_sim(years=SCENARIO["years"])
                s = score(r)
                results.append((s, um, em, r))
                
                print(f"  {um:>8}x {em:>7.0%} {r['burn_pct']:>7.1f}% {r['avg_weapon']:>6.1f} {r['maxed_pct']:>5.1f}% {r['players']:>7,} {s:>5.1f}")
            except Exception as e:
                print(f"  {um:>8}x {em:>7.0%} — 失败: {str(e)[:40]}")
    
    restore_constants()
    
    # TOP 10
    results.sort(key=lambda x: -x[0])
    print(f"\n{'=' * 90}")
    print(f"🏆  TOP 10 最佳参数组合")
    print(f"{'=' * 90}")
    print(f"  {'排名':>4} {'升级倍率':>8} {'日释放':>8} {'销毁率':>8} {'武器Lv':>7} {'满级%':>6} {'玩家':>8} {'总分':>6}")
    print(f"  {'-' * 4} {'-' * 8} {'-' * 8} {'-' * 8} {'-' * 7} {'-' * 6} {'-' * 8} {'-' * 6}")
    
    for rank, (s, um, em, r) in enumerate(results[:10], 1):
        print(f"  {rank:>4} {um:>8}x {em:>7.0%} {r['burn_pct']:>7.1f}% {r['avg_weapon']:>6.1f} {r['maxed_pct']:>5.1f}% {r['players']:>7,} {s:>5.1f}")
    
    print(f"\n{'=' * 90}")
    print("✅ 扫描完成")
    print(f"{'=' * 90}")


if __name__ == "__main__":
    main()
