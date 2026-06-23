"""Minimal ABIs for Dark Forest contracts."""

# ==============================
# DarkForest (core, via Proxy)
# ==============================

DARK_FOREST_ABI = [
    # -- write --
    {"name":"createCivilization","type":"function","stateMutability":"payable",
     "inputs":[{"name":"name","type":"string"}],"outputs":[]},
    {"name":"createCivilization","type":"function","stateMutability":"payable",
     "inputs":[{"name":"name","type":"string"},{"name":"referrer","type":"address"}],"outputs":[]},
    {"name":"upgradeSystem","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"sysId","type":"uint8"}],"outputs":[]},
    {"name":"collectEnergy","type":"function","stateMutability":"nonpayable",
     "inputs":[],"outputs":[]},
    {"name":"repairCollector","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"amount","type":"uint256"}],"outputs":[]},
    {"name":"repairAll","type":"function","stateMutability":"nonpayable",
     "inputs":[],"outputs":[]},
    {"name":"approveEnergy","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"outputs":[]},
    {"name":"transferEnergyFrom","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"from","type":"address"},{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"outputs":[]},
    {"name":"attack","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"target","type":"address"}],"outputs":[]},
    {"name":"repairShield","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"amount","type":"uint256"}],"outputs":[]},
    {"name":"assistShieldRepair","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"target","type":"address"},{"name":"amount","type":"uint256"}],"outputs":[]},
    {"name":"regenShield","type":"function","stateMutability":"nonpayable",
     "inputs":[],"outputs":[]},
    {"name":"spaceJump","type":"function","stateMutability":"nonpayable",
     "inputs":[],"outputs":[]},
    {"name":"trackingJump","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"target","type":"address"}],"outputs":[]},
    {"name":"startMove","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"x","type":"int256"},{"name":"y","type":"int256"},{"name":"z","type":"int256"}],"outputs":[]},
    {"name":"cancelMove","type":"function","stateMutability":"nonpayable",
     "inputs":[],"outputs":[]},
    {"name":"rebuildCivilization","type":"function","stateMutability":"nonpayable",
     "inputs":[],"outputs":[]},
    {"name":"claimCombatEnergy","type":"function","stateMutability":"nonpayable",
     "inputs":[],"outputs":[]},
    {"name":"claimDailyDFT","type":"function","stateMutability":"nonpayable",
     "inputs":[],"outputs":[]},
    {"name":"withdrawFees","type":"function","stateMutability":"nonpayable",
     "inputs":[],"outputs":[]},
    {"name":"withdrawFeesTo","type":"function","stateMutability":"nonpayable",
     "inputs":[],"outputs":[]},
    {"name":"setFeeRecipient","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"_feeRecipient","type":"address"}],"outputs":[]},
    {"name":"renounceOwnership","type":"function","stateMutability":"nonpayable",
     "inputs":[],"outputs":[]},
    {"name":"batchTransferAndBurn","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"from","type":"address"},{"name":"to","type":"address"},
              {"name":"transferAmount","type":"uint256"},{"name":"burnAmount","type":"uint256"}],"outputs":[]},
    {"name":"getCurrentPosition","type":"function","stateMutability":"view",
     "inputs":[{"name":"player","type":"address"}],
     "outputs":[{"components":[{"name":"x","type":"int256"},{"name":"y","type":"int256"},{"name":"z","type":"int256"}],"name":"pos","type":"tuple"},
               {"name":"isMoving","type":"bool"},{"name":"eta","type":"uint256"}]},

    # -- view --
    {"name":"getEntryFee","type":"function","stateMutability":"view",
     "inputs":[],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"getCivilization","type":"function","stateMutability":"view",
     "inputs":[{"name":"player","type":"address"}],
     "outputs":[{"components":[
         {"name":"name","type":"string"},{"name":"location","type":"tuple","components":[
             {"name":"x","type":"int256"},{"name":"y","type":"int256"},{"name":"z","type":"int256"}]},
         {"name":"energy","type":"uint256"},{"name":"health","type":"uint256"},
         {"name":"energyCollectorLv","type":"uint256"},{"name":"weaponLv","type":"uint256"},
         {"name":"radarLv","type":"uint256"},{"name":"shieldLv","type":"uint256"},{"name":"engineLv","type":"uint256"},
         {"name":"scanRange","type":"uint256"},{"name":"lastUpdateTime","type":"uint256"},
         {"name":"exists","type":"bool"},{"name":"isRuins","type":"bool"},{"name":"ruinsTimestamp","type":"uint256"}
     ],"type":"tuple"}]},
    {"name":"getCurrentShieldHP","type":"function","stateMutability":"view",
     "inputs":[{"name":"player","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"getMaxShieldHP","type":"function","stateMutability":"view",
     "inputs":[{"name":"player","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"getAttackEnergyCost","type":"function","stateMutability":"view",
     "inputs":[{"name":"player","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"getAttackPower","type":"function","stateMutability":"view",
     "inputs":[{"name":"player","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"getAttackTokenInfo","type":"function","stateMutability":"view",
     "inputs":[{"name":"player","type":"address"}],
     "outputs":[{"name":"tokens","type":"uint256"},{"name":"max","type":"uint256"},{"name":"interval","type":"uint256"},{"name":"rate","type":"uint256"}]},
    {"name":"getEnergyCollectRate","type":"function","stateMutability":"view",
     "inputs":[{"name":"player","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"getCollectorDurability","type":"function","stateMutability":"view",
     "inputs":[{"name":"player","type":"address"}],"outputs":[{"name":"current","type":"uint256"},{"name":"max","type":"uint256"}]},
    {"name":"getUpgradeCost","type":"function","stateMutability":"view",
     "inputs":[{"name":"player","type":"address"},{"name":"system","type":"string"}],
     "outputs":[{"name":"dft","type":"uint256"},{"name":"energy","type":"uint256"}]},
    {"name":"getBattleCount","type":"function","stateMutability":"view",
     "inputs":[],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"getPlayerCount","type":"function","stateMutability":"view",
     "inputs":[],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"getJumpCount","type":"function","stateMutability":"view",
     "inputs":[{"name":"player","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"getBattleHistory","type":"function","stateMutability":"view",
     "inputs":[{"name":"offset","type":"uint256"},{"name":"limit","type":"uint256"}],
     "outputs":[{"components":[
         {"name":"attacker","type":"address"},{"name":"defender","type":"address"},
         {"name":"timestamp","type":"uint256"},{"name":"damageDealt","type":"uint256"},
         {"name":"shieldDamage","type":"uint256"},{"name":"healthDamage","type":"uint256"},
         {"name":"stolenEnergy","type":"uint256"},{"name":"downgradedSystem","type":"string"},
         {"name":"attackerWon","type":"bool"}
     ],"type":"tuple[]"}]},
    {"name":"isInRange","type":"function","stateMutability":"view",
     "inputs":[{"name":"scanner","type":"address"},{"name":"target","type":"address"}],"outputs":[{"name":"","type":"bool"}]},
    {"name":"getDistance","type":"function","stateMutability":"view",
     "inputs":[{"name":"a","type":"address"},{"name":"b","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},

    # -- constants --
    {"name":"totalCivilizations","type":"function","stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"activeCivilizationCount","type":"function","stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"owner","type":"function","stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"address"}]},
    {"name":"gameStartTime","type":"function","stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"pendingCombatEnergy","type":"function","stateMutability":"view",
     "inputs":[{"name":"","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"referralCount","type":"function","stateMutability":"view",
     "inputs":[{"name":"","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"getCivilizations","type":"function","stateMutability":"view",
     "inputs":[{"name":"players","type":"address[]"}],
     "outputs":[{"components":[
         {"name":"name","type":"string"},{"name":"location","type":"tuple","components":[
             {"name":"x","type":"int256"},{"name":"y","type":"int256"},{"name":"z","type":"int256"}]},
         {"name":"energy","type":"uint256"},{"name":"health","type":"uint256"},
         {"name":"energyCollectorLv","type":"uint256"},{"name":"weaponLv","type":"uint256"},
         {"name":"radarLv","type":"uint256"},{"name":"shieldLv","type":"uint256"},{"name":"engineLv","type":"uint256"},
         {"name":"scanRange","type":"uint256"},{"name":"lastUpdateTime","type":"uint256"},
         {"name":"exists","type":"bool"},{"name":"isRuins","type":"bool"},{"name":"ruinsTimestamp","type":"uint256"}
     ],"type":"tuple[]"}]},
    {"name":"getSimpleStatuses","type":"function","stateMutability":"view",
     "inputs":[{"name":"players","type":"address[]"}],
     "outputs":[{"components":[
         {"name":"player","type":"address"},{"name":"energy","type":"uint256"},{"name":"health","type":"uint256"},
         {"name":"collectorLv","type":"uint256"},{"name":"weaponLv","type":"uint256"},
         {"name":"shieldLv","type":"uint256"},{"name":"radarLv","type":"uint256"},{"name":"engineLv","type":"uint256"},
         {"name":"shieldHP","type":"uint256"},{"name":"shieldMax","type":"uint256"},
         {"name":"exists","type":"bool"},{"name":"isRuins","type":"bool"}
     ],"type":"tuple[]"}]},
    {"name":"getPositions","type":"function","stateMutability":"view",
     "inputs":[{"name":"players","type":"address[]"}],
     "outputs":[{"components":[{"name":"x","type":"int256"},{"name":"y","type":"int256"},{"name":"z","type":"int256"}],"type":"tuple[]"},
                {"name":"moving","type":"bool[]"},{"name":"eta","type":"uint256[]"}]},
]

# ==============================
# DFT Token
# ==============================

ERC20_ABI = [
    {"name":"balanceOf","type":"function","stateMutability":"view",
     "inputs":[{"name":"","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"approve","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"spender","type":"address"},{"name":"amount","type":"uint256"}],"outputs":[{"name":"","type":"bool"}]},
    {"name":"transfer","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"outputs":[{"name":"","type":"bool"}]},
    {"name":"transferFrom","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"from","type":"address"},{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"outputs":[{"name":"","type":"bool"}]},
    {"name":"burn","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"amount","type":"uint256"}],"outputs":[]},
    {"name":"burnFrom","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"from","type":"address"},{"name":"amount","type":"uint256"}],"outputs":[]},
    {"name":"totalSupply","type":"function","stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"owner","type":"function","stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"address"}]},
]

DFT_ABI = ERC20_ABI + [
    {"name":"TOTAL_SUPPLY","type":"function","stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"DAILY_EMISSION","type":"function","stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"mint","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"outputs":[]},
    {"name":"setLiquidityPool","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"pool","type":"address"},{"name":"isPool","type":"bool"}],"outputs":[]},
    {"name":"setFeeCollectors","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"dev","type":"address"},{"name":"marketing","type":"address"}],"outputs":[]},
    {"name":"distributeFees","type":"function","stateMutability":"nonpayable","inputs":[],"outputs":[]},
]

# ==============================
# Energy Market
# ==============================

MARKET_ABI = [
    {"name":"getOrderCount","type":"function","stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"getActiveOrders","type":"function","stateMutability":"view",
     "inputs":[{"name":"offset","type":"uint256"},{"name":"limit","type":"uint256"}],
     "outputs":[{"components":[
         {"name":"seller","type":"address"},{"name":"energyAmount","type":"uint256"},
         {"name":"dftPrice","type":"uint256"},{"name":"active","type":"bool"}
     ],"type":"tuple[]"}]},
    {"name":"createOrder","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"energyAmount","type":"uint256"},{"name":"dftPrice","type":"uint256"}],"outputs":[]},
    {"name":"fillOrder","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"orderId","type":"uint256"}],"outputs":[]},
    {"name":"cancelOrder","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"orderId","type":"uint256"}],"outputs":[]},
    {"name":"withdrawDftFees","type":"function","stateMutability":"nonpayable",
      "inputs":[],"outputs":[]},
]

# ==============================
# Alliance
# ==============================

ALLIANCE_ABI = [
    {"name":"createAlliance","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"name","type":"string"}],"outputs":[]},
    {"name":"joinAlliance","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"id","type":"bytes32"}],"outputs":[]},
    {"name":"leaveAlliance","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"id","type":"bytes32"}],"outputs":[]},
    {"name":"kickMember","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"id","type":"bytes32"},{"name":"member","type":"address"}],"outputs":[]},
    {"name":"transferLeadership","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"id","type":"bytes32"},{"name":"newLeader","type":"address"}],"outputs":[]},
    {"name":"disbandAlliance","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"id","type":"bytes32"}],"outputs":[]},
    {"name":"claimRefund","type":"function","stateMutability":"nonpayable",
     "inputs":[{"name":"id","type":"bytes32"}],"outputs":[]},
    {"name":"playerAlliance","type":"function","stateMutability":"view",
     "inputs":[{"name":"","type":"address"}],"outputs":[{"name":"","type":"bytes32"}]},
    {"name":"isLeaveCooldownBlocked","type":"function","stateMutability":"view",
     "inputs":[{"name":"a","type":"address"},{"name":"b","type":"address"}],"outputs":[{"name":"","type":"bool"}]},
]
