# Improvement Roadmap

> Current score: 72/100 — see bottom for scoring breakdown.

## P0 — Blockers for production

| # | Item | Effort | Impact |
|---|------|:------:|:------:|
| 1 | **Signer 生产环境验证** — 在 BSC 测试网或主网启动 signer，通过 agent 远程发起真实交易 | 1d | 🔴 |
| 2 | **BSC 主网部署完成** — 解决 RPC 兼容性问题，验证所有 8 个合约，确认 ownership 链 | 2d | 🔴 |
| 3 | **合约操作手册** — 每个写函数列出：gas、能量消耗、DFT 消耗、前置条件、可能错误 | 1d | 🔴 |

## P1 — Signer security hardening

| # | Item | Effort | Impact |
|---|------|:------:|:------:|
| 4 | **TLS 证书轮换** — signer 启动时如果证书快过期自动警告 | 2h | 🟠 |
| 5 | **signer 健康检查端点暴露最小信息** — 当前 `/health` 暴露了 address、account label、rate_limit_remaining，考虑按 token 区分返回粒度 | 1h | 🟠 |
| 6 | **signer 异常重试逻辑** — 当前 `send_raw_transaction` 失败直接抛异常，加 3 次重试 + 指数退避 | 2h | 🟠 |
| 7 | **signer 的 `/sign-and-send` 返回更多元数据** — 返回 function selector、decoded function name，方便审计 | 1h | 🟡 |

## P2 — Agent quality

| # | Item | Effort | Impact |
|---|------|:------:|:------:|
| 8 | **`execute` 返回值标准化** — 当前 local 模式返回 dict，signer 模式返回 receipt，统一格式 | 1h | 🟠 |
| 9 | **ABI 自动同步 CI 检查** — CI 里跑 `generate_abi.py` 然后 `git diff --exit-code`，防止 ABI 漂移 | 1h | 🟠 |
| 10 | **批量 execute 接口** — 一次 RPC 调用发送多笔意图给 signer，signer 串行签名 | 3h | 🟡 |
| 11 | **函数参数类型自动校验** — `execute("game", "attack", ["0x..."])` 如果传了字符串而非以太坊地址，ABI 匹配时给出更好的错误提示 | 2h | 🟡 |

## P3 — Testing

| # | Item | Effort | Impact |
|---|------|:------:|:------:|
| 12 | **测试的 `try/except` → 全替换为 pre-check** — 剩余 ~5 个健壮性包装改为先查状态再断言 | 1h | 🟡 |
| 13 | **合约状态断言** — 不只看 `status == 1`，还要验证：攻击后 target 的 shield 应该降低、升级后 level 应该 +1 | 3h | 🟡 |
| 14 | **分叉测试** — forking BSC 主网测试 signer + agent 在生产状态下的行为 | 1d | 🟡 |
| 15 | **signer 集成测试** — 启动 signer 进程，Python agent 通过 HTTP 调 `/sign-and-send`，验证全链路 | 2h | 🟡 |

## P4 — Developer experience

| # | Item | Effort | Impact |
|---|------|:------:|:------:|
| 16 | **Type hints** — agent.py 所有公共方法加 type hints，方便 IDE 和 LLM 补全 | 2h | 🟢 |
| 17 | **pytest 骨架** — 把 test_integration.py 改为 pytest 参数化，可以只跑某个 section | 2h | 🟢 |
| 18 | **`df explain <function>`** — 查询合约函数的前置条件、消耗、参数说明 | 3h | 🟢 |
| 19 | **signer 内存安全** — `lock()` 后显式覆盖内存中的私钥字节（Python 用 `ctypes.memset`） | 1h | 🟢 |

## P5 — Documentation & Ops

| # | Item | Effort | Impact |
|---|------|:------:|:------:|
| 20 | **合约函数参考表** — Markdown 表：函数名、合约、gas 估计、能量/DFT 消耗、前置条件、可触发错误 | 3h | 🟠 |
| 21 | **架构设计文档** — agent ↔ signer ↔ RPC 的数据流图、安全边界、信任模型 | 2h | 🟠 |
| 22 | **signer 运维手册** — systemd unit 配置、日志轮转、TLS 配置、fail2ban 规则 | 2h | 🟠 |
| 23 | **Game Balance 文档** — 能量采集速度、升级公式、战斗伤害计算、跳的成本曲线 | 2h | 🟡 |

---

## Score breakdown

| Dimension | Current | Target | Gap |
|-----------|:------:|:------:|-----|
| Contracts | 75 | 80 | BSC 主网部署 |
| Agent architecture | 80 | 85 | type hints, batch execute |
| Signer security (design) | 75 | 75 | — |
| Integration testing | 72 | 85 | state assertions, fork tests |
| Maintainability (ABI) | 80 | 85 | CI check |
| Documentation | 45 | 70 | reference tables |
| Production readiness | 40 | 60 | BSC deploy + signer verify |
| **Overall** | **72** | **80** | |

Target: **80/100** after P0 + half of P1-P3 completed (~2 weeks).
