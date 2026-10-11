# 任务书：第 173 轮再返工 —— sol 177 的 M1-R1 与 S1（窗口 `luna-a` 续做）

sol 第 177 轮判 **FAIL**，报告 `review/rounds/round-177-g3h-fixes-review-codex.md`，先读全文。
其余部分（原 M1 产物问题、M2 两支校验器的拆分、固定基线、AST 扫描）已确认通过，**不要动**。
只改 `tests/test_tools_split_baseline.py`；`luna-c` 在改 `tests/contract/test_exam_index_port.py`，不要碰。

## 要改

1. **M1-R1**：`_require_html_inputs` 先调用 `workspace.require("materials.raw_root")`，整个
   `data/raw_materials` 缺失时抛 `ContractError`，走不到 `require_path`。改为：从注册表已解析的
   原始资料根路径（公开属性，如 `workspace.raw_root`——以 `ky/workspace.py` 实际公开接口为准）取路径，
   先交给 `require_path` 写明缺失路径与恢复来源（与本文件其它提示口径一致），再逐年检查 HTML。
   不要先用要求目录已存在的 `workspace.require`。
2. **S1**：给 round24 的固定基线对照加一个**双错误**输入（同一项 `status="approved"` 且 `sources=[]`），
   比较新旧版本错误列表与 CLI 三元组，使调换 `_validate_node_status_and_scope` 与
   `_validate_node_sources` 两个调用会变红。沿用 sol 177 探针的做法。

## 自证

- 干净归档：`git archive HEAD` 到系统临时目录，**不补** `data/raw_materials`，只复制本文件；设
  `GIT_DIR=<主库 .git>`、`PYTHONDONTWRITEBYTECODE=1`，跑 `py -3.12 -m unittest tests.test_tools_split_baseline -v`，
  不得有 ERROR / FAIL；贴 `Ran …` 行与每条跳过原因原文。
- 主仓库跑验收命令。
- 撤实现验证：临时副本里调换上述两个调用，确认新加的双错误对照变红；报告写实际命令与结果，恢复后核对哈希。

## 不做的

不改 `tools/`、`ky/`、`data/`；不新增任务书未列的测试；不跑全量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_tools_split_baseline tests.test_round24_weighted_tree
```

## 报告

`review/rounds/round-178-g3h-fixes2-luna.md`。写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。
不提交。含中文只用 `apply_patch`，写完查 `???`。
