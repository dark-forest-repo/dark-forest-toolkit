# Contract Function Reference

> Auto-generated from contract ABIs + integration test data.

## Game Operations (DarkForest via Proxy)

| Function | Inputs | Energy | DFT | ETH | Gas | Notes |
|----------|--------|:------:|:---:|:---:|:---:|-------|
| `approveEnergy` | address, uint256 | 0 | 0 | 0 | ~30k | sets allowance |
| `assistShieldRepair` | address, uint256 | cost | 0 | 0 | ~80k | alliance member only |
| `attack` | address | 2820 (lv1) | 0 | 0 | ~250k | needs token + range |
| `batchTransferAndBurn` | address, address, uint256, uint256 | 0 | 0 | 0 | ~80k | need allowance |
| `cancelMove` |  | 0 | 0 | 0 | ~30k |  |
| `claimCombatEnergy` |  | 0 | 0 | 0 | ~40k | E_NoPendingEnergy if none |
| `claimDailyDFT` |  | 0 | 0 | 0 | ~80k | once per day per player |
| `collectEnergy` |  | 0 | 0 | 0 | ~50k | adds energy based on time |
| `createCivilization` | string | 0 | 0 | ~0.01 entry fee | ~637k | payable; 1 per account |
| `createCivilization` | string, address | 0 | 0 | ~0.01 entry fee | ~637k | payable; 1 per account |
| `rebuildCivilization` |  | 5000 | varies | 0 | ~200k | must be ruins |
| `regenShield` |  | varies | 0 | 0 | ~60k |  |
| `repairAll` |  | varies | 0 | 0 | ~120k | sum of all repairs |
| `repairCollector` | uint256 | cost | 0 | 0 | ~60k |  |
| `repairShield` | uint256 | cost | 0 | 0 | ~80k | E_ShieldFull if max |
| `setFeeRecipient` | address | 0 | 0 | 0 | ~30k | owner only |
| `spaceJump` |  | 5000-150k | 3000-100k | 0 | ~300k | need dftToken.approve |
| `startMove` | int256, int256, int256 | cost | 0 | 0 | ~80k | E_TooFar if out of range |
| `trackingJump` | address | 5000-150k | 3000-100k | 0 | ~300k | need radar + range |
| `transferEnergyFrom` | address, address, uint256 | 0 | 0 | 0 | ~60k | need allowance |
| `upgradeSystem` | uint8 | varies | varies | 0 | ~300k | need dftToken.approve first |
| `withdrawFees` |  | 0 | 0 | 0 | ~40k | owner only |
| `withdrawFeesTo` |  | 0 | 0 | 0 | ~40k | anyone → to feeRecipient |

## Energy Market

| Function | Inputs | Energy | DFT | ETH | Gas | Notes |
|----------|--------|:------:|:---:|:---:|:---:|-------|
| `cancelOrder` | uint256 | 0 | 0 | 0 | ~50k | only seller can cancel |
| `createOrder` | uint256, uint256 | amount | 0 | 0 | ~120k | need approveEnergy |
| `fillOrder` | uint256 | 0 | price | 0 | ~150k | buyer pays DFT |
| `setFeeRecipient` | address | 0 | 0 | 0 | ~30k | owner only |
| `withdrawDftFees` |  | 0 | 0 | 0 | ~40k | admin |

## Alliance

| Function | Inputs | Energy | DFT | ETH | Gas | Notes |
|----------|--------|:------:|:---:|:---:|:---:|-------|
| `claimRefund` |  | 0 | 0 | 0 | ~40k |  |
| `createAlliance` | string | 0 | 0 | 0 | ~100k |  |
| `disbandAlliance` | bytes32 | 0 | 0 | 0 | ~60k | leader only |
| `joinAlliance` | bytes32 | 0 | 0 | 0 | ~80k |  |
| `kickMember` | bytes32, address | 0 | 0 | 0 | ~80k | leader only |
| `leaveAlliance` | bytes32 | 0 | cost | 0 | ~100k | need approve alliance contract |

## DFT Token Operations

| Function | Inputs | Energy | DFT | ETH | Gas | Notes |
|----------|--------|:------:|:---:|:---:|:---:|-------|
| `approve` | address, uint256 | 0 | 0 | 0 | ~40k | ERC20 |
| `burn` | uint256 | 0 | amount | 0 | ~40k | ERC20 |
| `burnFrom` | address, uint256 | 0 | amount | 0 | ~50k | need allowance |
| `distributeFees` |  | 0 | 0 | 0 | ~60k | anyone can call |
| `transfer` | address, uint256 | 0 | amount | 0 | ~50k | ERC20 |

## Energy Economy

| Parameter | Value |
|-----------|-------|
| `INITIAL_ENERGY` | 2000 |
| `BASE_COLLECT` | 3/sec |
| `DURABILITY_BASE` | 86400 (1 day) |
| `ATTACK_ENERGY_BASE` | 1000 |
| `ATTACK_ENERGY_PER_LV` | 2000 |
| `JUMP_ENERGY_BASE` | 5000 |
| `JUMP_ENERGY_PER_SQRT` | 5000 |
| `JUMP_ENERGY_MAX` | 150000 |
| `JUMP_DFT_BASE` | 3000 |
| `JUMP_DFT_PER_SQRT` | 3000 |
| `ENTRY_FEE_MIN` | 0.01 ETH |
| `ENTRY_FEE_MAX` | 0.05 ETH |
| `FEE_RAMP_UP_TIME` | 365 days |
