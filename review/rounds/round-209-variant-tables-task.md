# 任务书：技术债包 B 第三次返工 —— 变体表整表迁移（sol61 第 208 轮 R2-a / b / c，窗口 `luna-a` 续做）

sol61 第 208 轮判 FAIL：`review/rounds/round-208-baseline-harness-gaps2-review-sol61.md`。R1、R3、m1、m2 已通过，只剩 R2。
逐条"找等价"已经三轮仍有漏，**决策者改变做法**：不再逐条映射，改为把原变体表**整表迁移**成当前行为的表驱动测试。

## 做法

从 `git show f52b8f6:` 取三份原生成器：
- `tests/contract/test_models_split_baseline.py` 的 `_config_variants`、`_review_variants`；
- `tests/contract/test_workspace_split_baseline.py` 的 `_registry_variants`。

1. 把生成器（只含输入构造，不含任何旧版加载 / 新旧比较）搬到对应正规契约模块：config → `tests/contract/test_config_port.py`，
   review → `tests/test_contracts.py`（ReviewItem 部分），workspace → `tests/contract/test_workspace.py`。若生成器依赖的小辅助函数只在这里用，一并搬过来；
   跨模块共用的放 `tests/_fixtures.py`。
2. 每个**单错误**变体一条 `subTest`：断言**当前**代码的结果类别等于原表记录的期望（成功，或 `ContractError`），并断言错误路径（`ContractError.path`）
   **若原表 / 原比较里有路径期望**。期望值取自原表的 `expected_success` 等字段——不是现跑一遍再抄结果。
3. **只退役**纯为新旧首错次序比较而存在的"双错误 / paired error-order probe"变体（原表里明确是组合输入的那些），报告列出被退役的变体名。
4. 你第 207 轮新加的零散测试（revision=True、必填字段缺失、workspace 顶层块缺失）若被整表覆盖，删掉重复的，保留一种写法；报告说明。
5. m1（sol 208）：报告里的类 / 方法名一律写可定位的完整限定名。

## 证明

- 用 sol 208 的两处源码变异（临时 `ky/models.py` 副本：整数 `project_id` 先 `str()`；`last_quality` 上限 5 → 6）以及你自选的一处 workspace 变异
  （例如 `paper_shapes` 接受列表），在**临时 `ky/` 副本**里跑新表，必须变红；不要在测试侧 patch 被测函数。
- 报告给出三张表各自的变体总数、迁移数、退役数（数字从生成器实际产出统计，不写死进测试）。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_config_port tests.test_contracts tests.contract.test_workspace
```

## 报告

`review/rounds/round-209-variant-tables-luna.md`：迁移位置、退役变体清单与理由、变体计数、三处源码变异的命令与结果、验收输出原文。
临时文件只放系统临时目录。写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文只用 `apply_patch`，写完查 `???`。
