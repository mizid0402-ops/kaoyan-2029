# 评审任务书：第 178 轮 —— G3h 再返工（你第 177 轮的 M1-R1 / S1，窗口 `sol-main`）

请复审 `luna-a` 第 178 轮。任务书 `review/rounds/round-178-g3h-fixes2-task.md`，
实现报告 `review/rounds/round-178-g3h-fixes2-luna.md`，你上一轮报告 `review/rounds/round-177-g3h-fixes-review-codex.md`。

**本轮范围**：`tests/test_tools_split_baseline.py`（对 `58f44bc` 的完整 diff，重点是第 178 轮新改的部分），
以及确认 `tools/round24_validate_weighted_tree.py`、`tools/round29_validate_agreement.py` 与你第 177 轮审过的版本相同。
`tests/contract/test_exam_index_port.py` 已在第 179 轮 PASS，不在范围。

## 重点看

1. M1-R1：整个 `data/raw_materials` 缺失的干净归档里，模块无 ERROR / FAIL；HTML 成功场景按 `require_path`
   跳过并写明恢复来源；补回原始资料（不补登记产物）时，HTML 成功场景**实际运行**而非跳过。
2. S1：双错误对照确实锁住状态段与来源段的顺序（自己做调换变异确认变红）。
3. 第 178 轮没有顺带改动其他已通过的场景或断言。

## 规则

只跑与结论直接相关的单个模块或单条命令，**不跑全量**；复现用系统临时目录，不写进仓库。
结论 PASS / FAIL，分"必须改 / 建议改 / 不改"，每条附可复现输入；安全类单列"安全登记"。

## 报告

`review/rounds/round-180-g3h-fixes2-review-codex.md`。
