#!/usr/bin/env python3
"""
Dark Forest 能量经济全面扫描
============================
平衡目标：
  1. 攻击有利可图（但打低级玩家不划算）
  2. 能量不通胀（高等级玩家能量仍有价值）
  3. 修理成本有意义（占日产能合理比例）
  4. 整个 1-1000 级区间经济稳定

扫描维度：
  - DUR_PER_LV: 0, 3600, 21600, 86400 (秒)
  - ATTACK_COST_MUL: 攻击能耗公式调整
  - REPAIR_COST: 静态 vs 动态
  - JUMP_SCALE: 跳跃是否随等级增加
"""

import math
import sys
from copy import deepcopy

# ═══════════════════════════════════════
# 基线常量
# ═══════════════════════════════════════

BASE_COLLECT        = 3
COLLECT_BONUS       = 10
DUR_BASE            = 86400           # 1天

ATK_ENERGY_BASE     = 1000
ATK_ENERGY_PER_LV   = 2000

REPAIR_COST_PER_SEC = 1               # 1 能量/s
WEAPON_REPAIR_COST  = 2               # 2 能量
SHIELD_REPAIR_COST  = 2
ENGINE_REPAIR_COST  = 3

JUMP_ENERGY_BASE    = 5000
JUMP_ENERGY_PER_SQRT= 5000

PLUNDER_RATIO       = 3000            # 30%
ENERGY_BURN_BPS     = 500             # 5%

A = {"collector":5000,"weapon":10000,"shield":7000,"radar":8000,"engine":6000}
B = {"collector":5,"weapon":8,"shield":6,"radar":7,"engine":5}
MAX_LV = 1000
DAILY_EMISSION = 1_152_575_342
PLAYERS = 50000


def collect_rate(lv):
    return BASE_COLLECT if lv <= 1 else BASE_COLLECT + COLLECT_BONUS * math.sqrt(lv - 1)

def daily_energy(lv, dur_per_lv):
    dur = DUR_BASE + dur_per_lv * (lv - 1)
    return dur * collect_rate(lv)

def attack_cost(lv, base=ATK_ENERGY_BASE, per_lv=ATK_ENERGY_PER_LV):
    return base + per_lv * lv

def jump_cost(n=1):
    return JUMP_ENERGY_BASE + JUMP_ENERGY_PER_SQRT * int(math.sqrt(n))

def repair_collector_full(lv):
    dur = DUR_BASE
    return dur * REPAIR_COST_PER_SEC

def repair_weapon_full(lv):
    return (500 + 100 * (lv - 1)) * WEAPON_REPAIR_COST

def repair_shield_full(lv):
    return (259200 + 172800 * (lv - 1)) * SHIELD_REPAIR_COST

def repair_engine_full(lv):
    return (50 + 10 * (lv - 1)) * ENGINE_REPAIR_COST

def plunder_energy(victim_energy):
    return victim_energy * PLUNDER_RATIO // 10000

def total_daily_cost(lv, dur_per_lv):
    """一名活跃玩家一天的能量总消耗"""
    # 假设: 10次攻击, 2次跳跃, 1次全修
    atk_10 = 10 * attack_cost(lv)
    jump_2 = 2 * jump_cost(1)
    
    # 耐久修理
    col_rep = repair_collector_full(lv)
    wpn_rep = repair_weapon_full(lv) * 0.5  # 武器修一半
    shd_rep = repair_shield_full(lv) * 0.3  # 盾修30%
    eng_rep = repair_engine_full(lv) * 0.3
    
    return atk_10 + jump_2 + col_rep + wpn_rep + shd_rep + eng_rep


def score_config(dur_per_lv, atk_base, atk_per_lv, repair_ratio, jump_scale):
    """
    对一组参数打分(0-100)。
    分数越高,经济越健康。
    """
    scores = []
    
    for lv in [1, 5, 10, 20, 32, 50, 80, 100, 150, 200]:
        prod = daily_energy(lv, dur_per_lv)
        
        # 攻击成本
        atk = attack_cost(lv, atk_base, atk_per_lv)
        
        # 日常消耗总计
        repair_adj = repair_ratio  # 修理费缩放系数
        cost = (
            10 * atk +
            2 * jump_cost(1) * jump_scale +
            repair_collector_full(lv) * repair_adj +
            repair_weapon_full(lv) * 0.5 * repair_adj +
            repair_shield_full(lv) * 0.3 * repair_adj +
            repair_engine_full(lv) * 0.3 * repair_adj
        )
        
        # 能耗占比 = 日消耗 / 日产能
        usage = cost / prod * 100 if prod > 0 else 100
        
        # 攻击ROI: 掠夺对手30%能量 / 攻击能耗
        # 假设目标拥有平均日产能
        plunder = plunder_energy(prod)
        atk_roi = (plunder - atk) / atk if atk > 0 else 0
        
        # 攻击/天
        atk_per_day = prod / atk if atk > 0 else 0
        
        # ── 评分标准 ──
        s = 0
        
        # 1. 单次攻击有利可图(ROI > 20%)
        if atk_roi > 0.2:
            s += 20
        elif atk_roi > 0:
            s += 10 + (atk_roi / 0.2) * 10
        else:
            s += atk_roi * 50  # 负收益强惩罚
        
        # 2. 攻击/天在合理范围(50-3000)
        if 50 <= atk_per_day <= 3000:
            s += 20
        elif 20 <= atk_per_day < 50:
            s += 10 + (atk_per_day - 20) / 30 * 10
        elif 3000 < atk_per_day <= 6000:
            s += 10
        else:
            s += max(0, atk_per_day / 6000 * 5)
        
        # 3. 能耗占比 30-80%(能量既不闲置也不总是短缺)
        if 30 <= usage <= 80:
            s += 20
        elif 20 <= usage < 30:
            s += 10 + (usage - 20) / 10 * 10
        elif 80 < usage <= 95:
            s += 10
        else:
            s += usage / 20 * 5
        
        # 4. 修理费占产能的 5-20%
        repair_cost = repair_collector_full(lv) * repair_adj
        repair_pct = repair_cost / prod * 100 if prod > 0 else 100
        if 5 <= repair_pct <= 20:
            s += 20
        elif 2 <= repair_pct < 5:
            s += 10 + (repair_pct - 2) / 3 * 10
        elif 20 < repair_pct <= 40:
            s += 10
        else:
            s += repair_pct / 20 * 5
        
        # 5. 攻击/天跨等级稳定性(方差越小越好)
        # 在最后用整体方差评分
        
        scores.append((lv, s, usage, atk_roi, atk_per_day, repair_pct))
    
    # 整体稳定性评分
    atk_days = [s[4] for s in scores]
    if max(atk_days) > 0:
        stability = 1 - (max(atk_days) - min(atk_days)) / max(atk_days)
    else:
        stability = 0
    stability_score = stability * 15
    
    total = sum(s[1] for s in scores) / len(scores) + stability_score
    
    return {
        "total": total,
        "scores": scores,
        "stability": stability,
    }


def print_result(name, dur_per_lv, atk_base, atk_per_lv, repair_ratio, jump_scale):
    r = score_config(dur_per_lv, atk_base, atk_per_lv, repair_ratio, jump_scale)
    print(f"\n{'='*70}")
    print(f"📊  {name}")
    print(f"{'='*70}")
    print(f"  参数: DUR_PER_LV={dur_per_lv}s, ATK={atk_base}+{atk_per_lv}*lv, REPAIR={repair_ratio:.2f}x, JUMP={jump_scale:.1f}x")
    print(f"  总分: {r['total']:.1f}  |  稳定性: {r['stability']*100:.0f}%")
    print(f"\n  {'Lv':>4} {'日产能':>10} {'攻击/天':>7} {'攻击ROI':>8} {'能耗%':>6} {'修理%':>6} {'得分':>5}")
    print(f"  {'─'*4} {'─'*10} {'─'*7} {'─'*8} {'─'*6} {'─'*6} {'─'*5}")
    for lv, s, usage, atk_roi, atk_per_day, rep_pct in r["scores"]:
        roi_str = f"{atk_roi*100:+.0f}%" if atk_roi != 0 else " 0%"
        print(f"  {lv:>3} {daily_energy(lv, dur_per_lv):>9,.0f} {atk_per_day:>6.0f} {roi_str:>7} {usage:>5.1f}% {rep_pct:>5.1f}% {s:>4.1f}")
    return r["total"]


def scan():
    """扫描参数空间，寻找最优解"""
    print("=" * 70)
    print("🔬  Dark Forest 能量经济扫描")
    print("=" * 70)
    print(f"  玩家数: {PLAYERS:,}  |  最高等级: {MAX_LV}")
    print(f"  基线采集率: {BASE_COLLECT}/s + {COLLECT_BONUS}×√(lv-1)")
    print(f"  基线攻击能耗: {ATK_ENERGY_BASE} + {ATK_ENERGY_PER_LV}×lv")
    print()
    
    results = []
    
    # 扫描网格
    dur_vals = [0, 3600, 7200, 21600, 86400]
    atk_formulas = [
        ("1000+2000×lv", 1000, 2000),
        ("2000+3000×lv", 2000, 3000),
        ("1000+2500×lv", 1000, 2500),
        ("0+1500×lv^1.2", 0, 1500),  # 将最后评分时用指数公式加一列
    ]
    repair_vals = [1.0, 1.5, 2.0, 3.0]
    jump_vals = [1.0, 1.5, 2.0]
    
    print(f"扫描: {len(dur_vals)}×{4}×{len(repair_vals)}×{len(jump_vals)} = {len(dur_vals)*4*len(repair_vals)*len(jump_vals)} 组合")
    
    # 改为更精确的指数公式
    atk_formulas2 = [
        ("1000+2000×lv", 1000, 2000, 1.0),
        ("1500+2500×lv", 1500, 2500, 1.0),
        ("0+3000×lv^1.2", 0, 1500, 1.2),  # 指数公式: base + rate*lv^exp
        ("2000+1500×lv^1.15", 2000, 1500, 1.15),
    ]
    
    # 简化版扫描：关键组合
    combos = [
        # (name, dur_per_lv, atk_base, atk_per_lv, atk_exp, repair_ratio, jump_scale)
        ("当前(耐久O(lv))",   86400, 1000, 2000, 1.0, 1.0, 1.0),
        ("耐久固定(不涨)",   0, 1000, 2000, 1.0, 1.0, 1.0),
        ("耐久半涨",         3600, 1000, 2000, 1.0, 1.0, 1.0),
        ("耐久半涨+攻击翻倍", 3600, 2000, 3000, 1.0, 1.0, 1.0),
        ("耐久半涨+攻击指数", 3600, 0, 2500, 1.2, 1.0, 1.0),
        ("耐久半涨+修理×2",  3600, 1000, 2000, 1.0, 2.0, 1.0),
        ("耐久固定+攻击翻倍", 0, 2000, 3000, 1.0, 1.0, 1.0),
        ("耐久固定+跳跃×2",  0, 1000, 2000, 1.0, 1.0, 2.0),
        ("全面压制",         7200, 2000, 2500, 1.0, 2.0, 1.5),
    ]
    
    # 加上指数公式
    for atk_exp in [1.0, 1.15, 1.2, 1.3]:
        for dur in [3600, 21600]:
            name = f"指数{atk_exp:.1f}+耐久{dur//3600}h"
            combos.append((name, dur, 1000, 2000, atk_exp, 1.5, 1.0))
    
    # 特殊组合: DUR_PER_LV = 但攻击/天稳定
    for dur in [7200, 43200]:
        name = f"耐久{dur//3600}h+标准"
        combos.append((name, dur, 1000, 2000, 1.0, 1.5, 1.0))
    
    for name, dur, atk_base, atk_per_lv, atk_exp, repair_ratio, jump_scale in combos:
        # 攻击成本公式: atk_base + atk_per_lv * lv^atk_exp
        # 用动态求值
        def atk_cost_fn(lv, b=atk_base, p=atk_per_lv, e=atk_exp):
            return int(b + p * (lv ** e))
        
        # 评分
        scores_local = []
        for lv in [1, 5, 10, 20, 32, 50, 80, 100, 150, 200]:
            prod = daily_energy(lv, dur)
            atk = atk_cost_fn(lv)
            
            cost = (
                10 * atk +
                2 * jump_cost(1) * jump_scale +
                repair_collector_full(lv) * repair_ratio +
                repair_weapon_full(lv) * 0.5 * repair_ratio +
                repair_shield_full(lv) * 0.3 * repair_ratio +
                repair_engine_full(lv) * 0.3 * repair_ratio
            )
            
            usage = cost / prod * 100 if prod > 0 else 100
            plunder = plunder_energy(prod)
            atk_roi = (plunder - atk) / atk if atk > 0 else 0
            atk_per_day = prod / atk if atk > 0 else 0
            repair_cost = repair_collector_full(lv) * repair_ratio
            repair_pct = repair_cost / prod * 100 if prod > 0 else 100
            
            # 评分
            s = 0
            if atk_roi > 0.5: s += 25
            elif atk_roi > 0.2: s += 15 + (atk_roi - 0.2) / 0.3 * 10
            elif atk_roi > 0: s += 5 + atk_roi / 0.2 * 10
            else: s += max(-10, atk_roi * 30)
            
            if 30 <= atk_per_day <= 2000: s += 20
            elif 10 <= atk_per_day < 30: s += 10 + (atk_per_day - 10) / 20 * 10
            elif 2000 < atk_per_day <= 5000: s += 10
            else: s += atk_per_day / 5000 * 5
            
            if 30 <= usage <= 80: s += 20
            elif 20 <= usage < 30: s += 10 + (usage - 20) / 10 * 10
            elif 80 < usage <= 95: s += 10
            else: s += usage / 80 * 8
            
            if 5 <= repair_pct <= 20: s += 20
            elif 2 <= repair_pct < 5: s += 10 + (repair_pct - 2) / 3 * 10
            elif 20 < repair_pct <= 40: s += 10
            else: s += repair_pct / 20 * 5
            
            scores_local.append((lv, s, usage, atk_roi, atk_per_day, repair_pct))
        
        total = sum(s[1] for s in scores_local) / len(scores_local)
        atk_days = [s[4] for s in scores_local]
        stability = 1 - (max(atk_days) - min(atk_days)) / max(atk_days) if max(atk_days) > 0 else 0
        total += stability * 10
        
        results.append((total, name, dur, atk_exp, repair_ratio, scores_local))
    
    # 排序
    results.sort(key=lambda x: -x[0])
    
    print(f"\n{'='*70}")
    print(f"🏆  TOP 10 经济参数组合")
    print(f"{'='*70}")
    print(f"  {'排名':>4} {'总分':>6} {'方案':<30} {'耐久':>8} {'指数':>5} {'修理':>5}")
    print(f"  {'─'*4} {'─'*6} {'─'*30} {'─'*8} {'─'*5} {'─'*5}")
    for rank, (total, name, dur, atk_exp, repair_ratio, scores) in enumerate(results[:10], 1):
        print(f"  {rank:>3}  {total:>5.1f}  {name:<28} {dur//3600:>2}h   {atk_exp:.1f}x  {repair_ratio:.1f}x")
    
    # 展示最佳方案的详细数据
    print(f"\n{'='*70}")
    print(f"🏆  最优方案详情")
    best = results[0]
    _, name, dur, atk_exp, repair_ratio, scores = best
    print(f"  方案: {name}")
    print(f"  DUR_PER_LV={dur}s, ATK指数={atk_exp}, 修理比={repair_ratio}")
    print(f"\n  {'Lv':>4} {'日产能':>12} {'攻击/天':>7} {'攻击ROI':>8} {'能耗%':>6} {'修理%':>6}")
    print(f"  {'─'*4} {'─'*12} {'─'*7} {'─'*8} {'─'*6} {'─'*6}")
    for lv, s, usage, atk_roi, atk_per_day, rep_pct in scores:
        roi_str = f"{atk_roi*100:+.0f}%" if atk_roi != 0 else " 0%"
        print(f"  {lv:>3} {daily_energy(lv, dur):>11,.0f} {atk_per_day:>6.0f} {roi_str:>7} {usage:>5.1f}% {rep_pct:>5.1f}%")
    
    print(f"\n{'='*70}")
    print(f"✅ 扫描完成")
    print(f"{'='*70}")


if __name__ == "__main__":
    scan()
