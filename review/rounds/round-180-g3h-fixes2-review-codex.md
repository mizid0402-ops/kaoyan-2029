# 第 180 轮复审：G3h 第 178 轮再返工

## 结论

**PASS。** 第 177 轮 M1-R1 已修复：原始资料根目录完全不存在时，对照模块无 ERROR/FAIL，HTML 成功场景按资源缺失跳过；补入登记 HTML 后实际运行。S1 的双错误对照在调换两段检查顺序后变红。第 178 轮没有改动其他已通过场景或两支校验器。

只评 `tests/test_tools_split_baseline.py` 对 `58f44bc` 的 diff，并核对 `tools/round24_validate_weighted_tree.py`、`tools/round29_validate_agreement.py` 与第 177 轮版本相同。用 `git archive 58f44bc` 建系统临时树，复制当前测试文件和两支第 177 轮已审校验器；只在临时树运行及变异。第 179 轮卷面测试不在范围。全量：未跑（按 AGENTS.md）。

## 必须改

无。

## 建议改

无。

## 不改

- **M1-R1：整棵原始资料目录缺失。** 临时归档没有 `data/raw_materials`，也没有 `review/408知识点树与真题` 产物；设 `GIT_DIR=<主库 .git>`、`PYTHONDONTWRITEBYTECODE=1`，执行 `py -3.12 -m unittest tests.test_tools_split_baseline -v`，实测 `Ran 12 tests in 18.783s`、`OK (skipped=4)`，无 ERROR/FAIL。`test_html_extraction_success_uses_temporary_product_root` 单独跳过，原文提示为 `missing resource: <归档根>\data\raw_materials; restore registered raw materials from the acquisition source`。缺英语 PDF、登记 M21 产品索引、round24 来源缓存的三项各自跳过；NETEM/报告、参数失败、round24/29 其余对照均为 `ok`。代码从公开的 `workspace.raw_root` 得到路径，先交给 `require_path`，不再由 `workspace.require("materials.raw_root")` 提前抛契约异常。
- **HTML 成功支路确实执行。** 只把本机四份登记 `cs408_quiz_2023.html` 至 `cs408_quiz_2026.html` 复制到同一临时归档的原始资料目录，仍不补登记产物；单跑 `py -3.12 -m unittest tests.test_tools_split_baseline.ToolsSplitBaselineTests.test_html_extraction_success_uses_temporary_product_root -v`，实测 `Ran 1 test in 3.529s`、`OK`，该项为 `ok` 而非 skipped。测试沿用已审的代理：旧新版本读同一注册表及 HTML，只替换 products 根；每版清理临时输出后比较 `(退出码, stdout, stderr)` 和全部产物相对路径/原始字节。
- **S1 双错误顺序锁定。** 新测试在同一 weighted-tree 节点设置 `status="approved"` 和 `sources=[]`，比较固定 `58f44bc` 旧版与新版的 `validate` 错误列表、CLI 三元组，并断言前四条依次为状态不合法、禁止 `approved`、来源列表为空、来源数不符。原版测试在无原始资料的归档中为 `ok`。只在临时副本调换 round24 的 `_validate_node_status_and_scope` 与 `_validate_node_sources` 两次调用，设 `PYTHONDONTWRITEBYTECODE=1` 后单跑 `ValidatorSplitBaselineTests.test_round24_dual_error_order_matches_fixed_baseline`，实测 `FAILED (failures=1)`：第 448 行的旧新错误列表比较失败，变异版首条变为 `sources must be a non-empty list`。从工作区重复制校验器后，临时文件 SHA-256 与待审版相同，同一测试恢复为 `OK`。
- **改动边界。** 与第 177 轮保留的临时副本做逐字节比较，`round24_validate_weighted_tree.py` SHA-256 两边均为 `3ABD52A8BA10F22CE52BF8761C884DA515B76F5DA0CEBF3513133D28626BF38E`；`round29_validate_agreement.py` 两边均为 `6084D2FC19CF429449BF4E124D9372C53950E6ECDD86AF365F61BB61B9EE8226`。`tests/test_tools_split_baseline.py` 相对第 177 轮版本只有两个增量：把 raw-root 检查改成 `workspace.raw_root` 加 `require_path`，以及新增 round24 双错误方法；其余场景和断言逐字节未改。

## 安全登记

本轮未发现需按恶意输入、手工篡改内部文件或精确竞态登记的新问题。
