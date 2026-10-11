# 任务书：技术债包 B 续做（窗口 `luna-a` 续做第 200 轮）

你在第 200 轮如实写明未完成，谢谢。盘点、harness 初版与四份配置视图收敛都保留；本轮把剩下的做完。
任务书仍是 `review/rounds/round-200-baseline-harness-task.md`，本文件只补充决策者的裁定。`ky/` 由另一个窗口在做，**不要碰**。

## 决策者裁定

1. **(b) 类的处理口径**：你的盘点里几乎每个方法都是 "a,b"。多数 (b) 是**对照场景的附带断言**（"成功时退出码 0"、"失败时没写完成事件"）。
   逐条判断：
   - 若它断言的行为**在正规测试模块里已有等价断言**（按 `docs/模块地图.md` 找该端口的契约测试 / `tests/test_cli.py` 等），写明等价的是哪个测试方法，**不迁**；
   - 若没有，迁到对应正规模块，写成**不依赖旧版**的直接断言（同样的输入、同样的期望），在新位置运行通过；
   - 若它只在"与旧版对照"这个语境下有意义（例如"两版错误顺序相同"），就随实例退役，报告里写明理由。
   报告给出逐条去向表：原文件::方法::断言 → 已有等价（指向谁）/ 迁到哪（新测试名）/ 随退役（理由）。
2. **保留实例**：选 1–2 个，改写成基于 `tests/_baseline_harness.py` 的实例（挑输入小、被测代码稳定的；例如 `test_state_snapshot_counts_baseline` 这类纯函数对照）。
   等价证明照原任务书第 4 步：每个保留实例至少两处定点变异，**原文件与改写后都要变红**，未变异时都通过。
3. **去掉 `_LegacyConfigView` 别名**：四个契约测试改为直接引用 `tests/_fixtures.py` 里的公开名（`AGENTS.md`：不留兼容别名）。
4. `_write_registry`、`make_item`、`run_cli`：若 9 个文件退役后这些辅助只剩一个使用者，就不必再提取；只收敛**退役后仍跨文件重复**的。
5. 完成以上后删除其余 A 类文件，测退役后的耗时。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_baseline_harness <保留实例模块> <迁入断言的各模块> tests.contract.test_planner_port tests.contract.test_availability_port tests.contract.test_freeze_port tests.contract.test_day_budget_port
```

## 报告

`review/rounds/round-203-baseline-harness-continue-luna.md`：(b) 去向表、保留实例与变异证明（命令与结果）、别名移除、辅助收敛结果、删除清单、退役前后耗时、验收输出原文。
有未完成的如实写明，**未完成时不要删除任何 A 类文件**。写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文只用 `apply_patch`，写完查 `???`。
