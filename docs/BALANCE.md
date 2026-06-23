# Game Balance Reference

## Entry Fee

| Constant | Value | Formula |
|----------|-------|---------|
| `ENTRY_FEE_MIN` | 0.01 ETH | Day 0 |
| `ENTRY_FEE_MAX` | 0.05 ETH | Day 365 |
| `FEE_RAMP_UP_TIME` | 365 days | linear |

```
fee(day) = 0.01 + 0.04 * min(day, 365) / 365
```

## Civilization

| Constant | Value |
|----------|-------|
| `INITIAL_ENERGY` | 2000 |
| `INITIAL_HEALTH` | 1000 |
| `INITIAL_SCAN_RANGE` | 1000 |
| `MAX_HEALTH` | 20,000 |
| `REFERRAL_ENERGY_REWARD` | 150 per side |

## Energy Collection

| Constant | Value |
|----------|-------|
| `BASE_COLLECT` | 3/sec |
| `COLLECT_BONUS` | 10 |
| `DURABILITY_BASE` | 86,400 sec (1 day) |
| `DURABILITY_PER_LV` | 86,400 sec (1 day) |
| `REPAIR_COST_PER_SEC` | 1 energy per sec |

```
collect_rate(lv, refs) = base * (1000 + refs * 2) / 1000
  base = 3 (lv ≤ 1)  or  3 + 10 * sqrt(lv - 1)
```

## Combat

| Constant | Value | Description |
|----------|-------|-------------|
| `ATK_BASE` | 900 | Base attack power |
| `ATK_RATE` | 10 | Scaling: `900 + 10*lv²` |
| `DEF_BASE` | 540 | Base defense |
| `DEF_RATE` | 6 | Scaling: `540 + 6*lv²` |
| `ATTACK_ENERGY_BASE` | 1000 | Base energy cost |
| `ATTACK_ENERGY_PER_LV` | 2000 | Per weapon level |
| `PLUNDER_RATIO` | 3000 (30%) | Energy stolen |
| `DESTRUCTION_RATE` | 4000 (40%) | Health threshold for kill |
| `DOWNGRADE_DIVISOR` | 10 | `lv / 10` on defeat |
| `SHIELD_DMG_BONUS` | 200 | Bonus damage vs shields |
| `LAST_HIT_BONUS_PERCENT` | 50 | Last hit damage bonus |

```
attack_cost = 1000 + 2000 * weapon_lv
attack_power = 900 + 10 * weapon_lv²
defense = 540 + 6 * shield_lv²
```

### Attack Token Bucket

| Constant | Value |
|----------|-------|
| `TOKEN_BASE_MAX` | 3 (at Lv 1) |
| `TOKEN_MAX_CAP` | 10 |
| `TOKEN_INTERVAL_MS_BASE` | 300ms |
| `TOKEN_INTERVAL_REDUCTION` | 10ms/lv |
| `TOKEN_MIN_INTERVAL` | 1 sec |
| `TOKEN_BASE_INTERVAL` | 3 sec |

```
interval = max(300 - 10*lv, 100) / 100  seconds
max_tokens = min(3 + lv/10, 10)
```

## Shield

| Constant | Value | Formula |
|----------|-------|---------|
| `SHIELD_HP_BASE` | 3600 | |
| `SHIELD_HP_RATE` | 15 | `3600 + 15*lv²` |
| `REGEN_BASE` | 50 | |
| `REGEN_RATE` | 1 | `50 + 1*lv²` |
| `SHIELD_REGEN_ENERGY_RATIO` | 1 | 1 energy → 1 shield HP |
| `SHIELD_REPAIR_COST` | 2 | energy per point |

## Space Jump

| Constant | Value | Formula |
|----------|-------|---------|
| `JUMP_ENERGY_BASE` | 5000 | |
| `JUMP_ENERGY_PER_SQRT` | 5000 | `min(5000+5000*√jc, 150000)` |
| `JUMP_ENERGY_MAX` | 150,000 | |
| `JUMP_DFT_BASE` | 3000 | |
| `JUMP_DFT_PER_SQRT` | 3000 | `min(3000+3000*√jc, 100000)` |
| `JUMP_DFT_MAX` | 100,000 | |
| `JUMP_COOLDOWN` | 3600s (1 hour) | |
| `JUMP_TRACKING_RADAR_LV` | 20 | required for tracking jump |

## Upgrades

| System | A (UP_A) | B (UP_B) | Cost Formula |
|--------|:--------:|:--------:|--------------|
| Collector | 500 | 5 | `500 * lv * (lv+5) / 100` DFT |
| Weapon | 1000 | 8 | `1000 * lv * (lv+8) / 100` DFT |
| Shield | 700 | 6 | `700 * lv * (lv+6) / 100` DFT |
| Radar | 800 | 7 | `800 * lv * (lv+7) / 100` DFT |
| Engine | 600 | 5 | `600 * lv * (lv+5) / 100` DFT |

Energy cost = DFT cost / 2. Must approve proxy for `burnFrom` first.

## Durability (per system)

| System | Base | Per LV | Repair Cost |
|--------|:----:|:------:|:-----------:|
| Collector | 86,400 (1d) | 86,400 (1d) | 1 energy/sec |
| Weapon | 500 | 100 | 2 energy |
| Shield | 259,200 (3d) | 172,800 (2d) | 2 energy |
| Engine | 50 | 10 | 3 energy |

## Engine (Cruise)

| Constant | Value | Formula |
|----------|-------|---------|
| `ENGINE_SPEED_BASE` | 10 | |
| `ENGINE_SPEED_PER_LV` | 5 | `10 + 5*(lv-1)` for lv ≥ 2 |

## Radar

| Constant | Value | Formula |
|----------|-------|---------|
| `RADAR_BASE` | 1000 | |
| `RADAR_LINEAR` | 150 | `1000 + 150*lv + 5*lv²` |
| `RADAR_QUAD` | 5 | |

## Alliance

| Constant | Value |
|----------|-------|
| `MAX_ALLIANCE_NAME` | 32 chars |
| `MAX_MEMBERS` | 100 |
| `LEAVE_COST_BASE` | 100 DFT |
| `LEAVE_COST_PER_MEMBER` | 10 DFT |
| `LEAVE_COOLDOWN` | 24 hours |

## DFT Token

| Constant | Value |
|----------|-------|
| `TOTAL_SUPPLY` | 4,206,900,000,000 |
| `DAILY_EMISSION` | 1,152,575,342 |
| `EMISSION_DAYS` | 3650 (~10 years) |
| `DEV_FEE_BPS` | 100 (1%) |
| `MARKETING_FEE_BPS` | 150 (1.5%) |
| `TOTAL_FEE_BPS` | 250 (2.5%) |
