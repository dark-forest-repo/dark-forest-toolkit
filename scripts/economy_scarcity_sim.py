#!/usr/bin/env python3
"""
Dark Forest 经济稀缺性模拟器
============================
基于聚合经济模型（dark_forest_econ_sim.Sim），
分析 DFT 供应 vs 消耗的稀缺性动态。

核心问题：
  1. 在 N 个玩家争夺每日释放的 DFT 时，升级需求能否创造稀缺？
  2. 供给 vs 需求达到平衡时，玩家平均等级是多少？
  3. 10 年后的经济是通缩还是通胀？

用法:
  python3 scripts/economy_scarcity_sim.py
"""

import math
import sys
import os

# 保证能导入同级模块
sys.path.insert(0, os.path.dirname(__file__))
from dark_forest_econ_sim import Sim, Cohort, TOTAL_DFT, DAILY_EMISSION
from dark_forest_econ_sim import up_cost as upgrade_cost, UPGRADE_COST_PARAMS

# ═══════════════════════════════════════════════════════
# 场景定义
# ═══════════════════════════════════════════════════════

SCENARIOS = [
    {
        "name": "🟢 基准 — 5万玩家，中速增长",
        "initial": 50000,
        "growth_rate": 0.003,
        "max_players": 500000,
    },
    {
        "name": "🔵 爆发 — 1万玩家，高速增长",
        "initial": 10000,
        "growth_rate": 0.015,
        "max_players": 500000,
    },
    {
        "name": "🟣 小众 — 1000玩家，低增长",
        "initial": 1000,
        "growth_rate": 0.001,
        "max_players": 50000,
    },
    {
        "name": "🟠 饱和 — 20万玩家，零增长",
        "initial": 200000,
        "growth_rate": 0.0,
        "max_players": 200000,
    },
]

# 玩家风格分布
STYLE_DIST = [
    ("farmer",  0.40, 0.002),   # 40% 休闲农民，日流失 0.2%
    ("fighter", 0.35, 0.005),   # 35% 战斗型，日流失 0.5%
    ("whale",   0.15, 0.001),   # 15% 重度玩家，日流失 0.1%
    ("flipper", 0.10, 0.01),    # 10% 投机型，日流失 1%
]


def run_scenario(scenario: dict) -> dict:
    """运行一个场景并返回关键经济指标"""
    n = scenario["initial"]
    sim = Sim(
        players=[
            Cohort(
                count=int(n * pct),
                style=style,
                churn_pct=churn,
            )
            for style, pct, churn in STYLE_DIST
        ]
    )
    # 设置增长
    sim.growth_rate = scenario["growth_rate"]
    sim.max_players = scenario["max_players"]
    
    sim.run(years=10)
    
    # 收集结果
    last_day = sim.day
    t = sim.total_count()
    burned_ratio = sim.dft_burned / max(sim.dft_minted, 1)
    
    # 计算平均等级
    avg_lvs = {}
    if t > 0:
        for attr, name in [("lv_c", "collector"), ("lv_w", "weapon"),
                           ("lv_s", "shield"), ("lv_r", "radar"), ("lv_e", "engine")]:
            avg_lvs[name] = sum(getattr(c, attr) * c.count for c in sim.players) / t
    
    # 满级玩家数
    maxed = sum(c.count for c in sim.players if c.is_maxed)
    
    # 每日平均 DFT 消耗（燃烧）
    daily_burn = sim.dft_burned / max(last_day, 1)
    daily_mint = DAILY_EMISSION
    
    return {
        "name": scenario["name"],
        "days": last_day,
        "years": last_day / 365,
        "final_players": t,
        "dft_minted": sim.dft_minted,
        "dft_burned": sim.dft_burned,
        "dft_circulating": sim.dft_circulating,
        "burned_pct": burned_ratio,
        "daily_burn": daily_burn,
        "daily_mint": daily_mint,
        "avg_lvs": avg_lvs,
        "maxed": maxed,
        "maxed_pct": maxed / t if t > 0 else 0,
        "energy_produced": sim.energy_produced,
        "energy_consumed": sim.energy_consumed,
        "battles": sim.battles,
        "jumps": sim.jumps,
        "market_volume": sim.market_volume,
        "market_burned": sim.market_burned,
    }


def scarcity_analysis(scenarios_results: list):
    """对多场景输出一致性稀缺分析"""
    print("\n" + "=" * 75)
    print("📊  稀 缺 性 跨 场 景 对 比")
    print("=" * 75)
    
    header = f"{'场景':<30} {'玩家':>8} {'铸造(亿)':>10} {'销毁(亿)':>10} {'销毁率':>8} {'采集':>5} {'武器':>5} {'满级%':>6}"
    print(header)
    print("-" * 75)
    
    for r in scenarios_results:
        print(
            f"{r['name']:<30} "
            f"{r['final_players']:>8,} "
            f"{r['dft_minted']/1e8:>10.1f} "
            f"{r['dft_burned']/1e8:>10.1f} "
            f"{r['burned_pct']:>7.1%} "
            f"{r['avg_lvs'].get('collector', 0):>5.1f} "
            f"{r['avg_lvs'].get('weapon', 0):>5.1f} "
            f"{r['maxed_pct']:>5.1%}"
        )
    
    print("\n" + "=" * 75)
    print("📈  稀 缺 性 指 标 评 估")
    print("=" * 75)
    
    for r in scenarios_results:
        name = r["name"]
        bp = r["burned_pct"]
        avg_lv = r["avg_lvs"].get("weapon", 0)
        maxed_pct = r["maxed_pct"]
        t = r["final_players"]
        
        print(f"\n  {name}")
        print(f"  {'─' * 50}")
        
        # 1. 燃烧率
        print(f"  燃烧率: {bp:.1%}", end="")
        if bp > 40:
            print(" → 🟢 强通缩（超过 40% DFT 被销毁）")
        elif bp > 20:
            print(" → 🟢 健康通缩（20-40% 被销毁）")
        elif bp > 5:
            print(" → 🟡 微弱通缩（5-20% 被销毁）")
        else:
            print(" → 🔴 通胀风险（低于 5% 被销毁）")
        
        # 2. 平均等级
        print(f"  平均武器等级: {avg_lv:.1f}", end="")
        if avg_lv >= 30:
            print(" → 🟡 等级过高，升级动力可能耗尽")
        elif avg_lv >= 15:
            print(" → 🟢 健康的中位等级")
        else:
            print(" → 🟢 早期发展，增长空间大")
        
        # 3. 满级比例
        print(f"  满级玩家占比: {maxed_pct:.1%}", end="")
        if maxed_pct > 0.5:
            print(" → 🔴 过半玩家满级，游戏缺乏长期目标")
        elif maxed_pct > 0.2:
            print(" → 🟡 部分玩家满级，需要持续释放新内容")
        else:
            print(" → 🟢 大多数玩家仍有升级空间")
        
        # 4. 供需平衡
        if t > 0:
            # 估算每个玩家每天的升级需求
            avg_upgrade_cost_daily = 0
            for sys_name, param in UPGRADE_COST_PARAMS.items():
                A, B = param
                lv = r["avg_lvs"].get(
                    {"Collector": "collector", "Weapon": "weapon",
                     "Shield": "shield", "Radar": "radar", "Engine": "engine"}.get(sys_name, sys_name.lower()),
                    1)
                cost_per_level = A * lv * (lv + B) / 100  # 下一级所需DFT
                avg_upgrade_cost_daily += cost_per_level
            
            total_annual_demand = avg_upgrade_cost_daily * t * 365
            annual_supply = DAILY_EMISSION * 365
            scarcity_ratio = total_annual_demand / annual_supply if annual_supply > 0 else 0
            
            print(f"  年化需求(估算): {total_annual_demand/1e8:.1f}亿 DFT", end="")
            print(f" | 年化供给: {annual_supply/1e8:.1f}亿 DFT", end="")
            print(f" | 供需比: {scarcity_ratio:.2f}x", end="")
            if scarcity_ratio > 2:
                print(" → 🟢 强需求，DFT 稀缺")
            elif scarcity_ratio > 1:
                print(" → 🟡 需求略高于供给")
            else:
                print(" → 🔴 供给过剩")
        
        # 5. 玩家数相对
        print(f"  最终玩家数: {t:,}", end="")
        print(f" | {'活跃游戏' if t > 10000 else '可玩' if t > 1000 else '⚠️ 可能鬼服'}")


def main():
    print("=" * 75)
    print("🌲  Dark Forest — 经济稀缺性模拟器")
    print("=" * 75)
    print(f"  DFT 总量: {TOTAL_DFT/1e8:.2f}亿")
    print(f"  每日释放: {DAILY_EMISSION:,} /天")
    print(f"  释放周期: 10 年 (3650 天)")
    print()
    
    results = []
    for sc in SCENARIOS:
        print(f"\n📌 运行: {sc['name']}")
        print(f"  {'─' * 50}")
        try:
            r = run_scenario(sc)
            results.append(r)
        except Exception as e:
            print(f"  ❌ 失败: {e}")
    
    if results:
        scarcity_analysis(results)
    
    print("\n" + "=" * 75)
    print("✅ 模拟完成")
    print("=" * 75)


if __name__ == "__main__":
    main()
