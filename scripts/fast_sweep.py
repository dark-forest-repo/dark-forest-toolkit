#!/usr/bin/env python3
"""
Dark Forest 参数快速扫描

基于合约实际常量，不依赖 buggy 的 Sim 类。
快速扫描升级倍率 + 日释放组合，找出最优参数。

运行: python3 scripts/fast_sweep.py  (约 30 秒)
"""

import math, sys, time
from typing import List

# ══════════════════════════════════════
# 合约常量（精确）
# ══════════════════════════════════════

TOTAL_DFT       = 4_206_900_000_000
DAILY_EMISSION  = 1_152_575_342      # 合约值
INITIAL_MINT    = 1_000_000          # 初始铸造

UPGRADE_COST = {
    "collector": (500, 5), "weapon": (1000, 8), "shield": (700, 6),
    "radar": (800, 7), "engine": (600, 5),
}

BASE_COLLECT   = 3
COLLECT_BONUS  = 10
DUR_BASE       = 86400
DUR_PER_LV     = 86400
DURABILITY_MAX = 86400  # 每天最多采集 1 天耐力

MAX_LV = 1000


def up_cost(system: str, lv: int) -> int:
    A, B = UPGRADE_COST[system]
    return max(1, A * lv * (lv + B) // 100)


def collect_rate(lv: int) -> float:
    base = BASE_COLLECT if lv <= 1 else BASE_COLLECT + COLLECT_BONUS * math.sqrt(lv - 1)
    return base


def simulate(
    players: int = 50000,
    years: int = 10,
    upgrade_mul: float = 1.0,
    emission_mul: float = 1.0,
) -> dict:
    """
    经济模拟（群体聚合模型）。

    假设所有玩家同质（相同进度），用 N 个玩家的平均行为代表全体。
    这是合理的近似，因为玩家行为差异在大量玩家下会收敛。

    返回 10 年后的经济状态。
    """
    day_emission = int(DAILY_EMISSION * emission_mul)
    total_minted = INITIAL_MINT
    total_burned = 0
    n = players

    # 玩家状态（平均）
    lvs = {s: 1 for s in UPGRADE_COST}
    energy = 2000.0
    dft = 1000.0  # 初始 DFT（从初始铸造分配）

    for day in range(1, years * 365 + 1):
        # 每日释放
        remaining = TOTAL_DFT - total_minted
        if remaining <= 0:
            break
        daily = min(day_emission, remaining)
        total_minted += daily

        # 每个玩家领取
        per_player = daily / n
        dft += per_player

        # 采集能量
        dur = DUR_BASE + DUR_PER_LV * (lvs["collector"] - 1)
        max_collect = dur * collect_rate(lvs["collector"])
        collected = min(max_collect, DURABILITY_MAX * collect_rate(lvs["collector"]))
        energy += collected

        # 升级
        # 优先级: 采集 > 武器 > 盾 > 引擎 > 雷达
        for sys in ["collector", "weapon", "shield", "engine", "radar"]:
            # 每个系统每天最多升 5 级（加快演化速度）
            for _ in range(5):
                if lvs[sys] >= MAX_LV:
                    break
                cost = int(up_cost(sys, lvs[sys]) * upgrade_mul)
                if dft >= cost and energy >= cost / 2:
                    dft -= cost
                    energy -= cost / 2
                    total_burned += cost
                    lvs[sys] += 1
                else:
                    break

        # 攻击消耗（偶尔）
        if day % 7 == 0 and energy > 5000:
            energy -= 3000  # 一次攻击

        # 跳跃消耗（偶尔）
        if day % 30 == 0 and energy > 10000:
            dft -= 6000  # 第一跳 DFT 成本
            total_burned += 6000
            energy -= 10000  # 第一跳能量成本

    burn_pct = total_burned / total_minted * 100 if total_minted > 0 else 0
    avg_lv = sum(lvs.values()) / len(lvs)

    return {
        "n": n,
        "years": years,
        "minted": total_minted,
        "burned": total_burned,
        "burn_pct": burn_pct,
        "avg_lv": avg_lv,
        "lvs": lvs,
    }


def score(r: dict, n: int = 50000) -> float:
    """评分函数。理想结果在 80-100 分。"""
    bp = r["burn_pct"]
    al = r["avg_lv"]
    s = 0.0

    # 销毁率：目标 40-80%
    if 40 <= bp <= 80: s += 35
    elif 25 <= bp < 40: s += 20 + (bp - 25) / 15 * 15
    elif 80 < bp <= 90: s += 20
    elif 15 <= bp < 25: s += 10
    else: s += bp / 15 * 5

    # 平均等级：目标 10-30（10年）
    if 10 <= al <= 30: s += 35
    elif 30 < al <= 45: s += 20 - (al - 30) / 15 * 10
    elif 5 <= al < 10: s += 15 + (al - 5) / 5 * 15
    else: s += 2

    # 惩罚极端值
    if al >= 45: s -= (al - 45) / 5 * 2  # 等级太高，升级曲线斜率不够
    if bp > 95: s -= 10                  # 销毁太多，经济枯竭
    if bp < 1: s = 0                      # 几乎没销毁，无意义

    return max(0, s)


def sweep():
    print("=" * 100)
    print("🔬  Dark Forest 参数快速扫描")
    print("=" * 100)
    print(f"\n合约常量: TOTAL={TOTAL_DFT:,}, DAILY_EMISSION={DAILY_EMISSION:,}")
    print(f"扫描参数: N=50000玩家, 10年\n")
    print(f"  {'UpMul':>6} {'EmMul':>7} {'销毁%':>7} {'平均Lv':>7} {'铸造(亿)':>10} {'销毁(亿)':>10} {'评分':>6}")
    print(f"  {'─'*6} {'─'*7} {'─'*7} {'─'*7} {'─'*10} {'─'*10} {'─'*6}")

    results = []
    for um in [1, 2, 3, 5, 8, 12, 20]:
        for em in [1.0, 0.5, 0.3, 0.15, 0.08, 0.04]:
            r = simulate(players=50000, years=10, upgrade_mul=um, emission_mul=em)
            s = score(r)
            results.append((s, um, em, r))
            print(f"  {um:>4}x {em:>6.0%} {r['burn_pct']:>6.1f}% {r['avg_lv']:>6.1f} "
                  f"{r['minted']/1e8:>9.1f} {r['burned']/1e8:>9.1f} {s:>5.1f}")

    results.sort(key=lambda x: -x[0])

    print(f"\n{'=' * 100}")
    print("🏆  TOP 5 最佳参数")
    print(f"{'=' * 100}")
    print(f"  {'排名':>4} {'UpMul':>6} {'EmMul':>7} {'销毁%':>7} {'平均Lv':>7} {'铸造(亿)':>10} {'销毁(亿)':>10} {'评分':>6}")
    print(f"  {'─'*4} {'─'*6} {'─'*7} {'─'*7} {'─'*7} {'─'*10} {'─'*10} {'─'*6}")

    for rank, (s, um, em, r) in enumerate(results[:5], 1):
        lvs_str = " ".join(f"{s}={r['lvs'][s]:.0f}" for s in UPGRADE_COST)
        print(f"  {rank:>4} {um:>4}x {em:>6.0%} {r['burn_pct']:>6.1f}% {r['avg_lv']:>6.1f} "
              f"{r['minted']/1e8:>9.1f} {r['burned']/1e8:>9.1f} {s:>5.1f}")
        if rank == 1:
            print(f"  ──> 各系统等级: {lvs_str}")
            print(f"  ──> 建议: A系数 × {um}, 日释放 × {em:.0%}")

    return results


if __name__ == "__main__":
    t0 = time.time()
    results = sweep()
    t = time.time() - t0
    print(f"\n扫描完成: {len(results)} 组, 耗时 {t:.1f} 秒")
