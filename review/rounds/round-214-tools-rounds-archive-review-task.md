# 评审任务书：技术债包 C —— `tools/` 轮次脚本归档与写死路径（第 213 轮，窗口 `sol61-main`）

请评审 `luna-b` 第 213 轮：任务书 `review/rounds/round-213-tools-rounds-archive-task.md`，报告 `review/rounds/round-213-tools-rounds-archive-luna.md`。
背景：`docs/技术债与整改清单.md` P2-1 / P2-2 与 §9。范围：`git diff ab56529 -- tools tests` 与新增的 `tools/` 文件。

## 重点看

1. **纯移动**：`tools/cs408_outline_extract.py`、`tools/cs408_quote_locate.py` 里的函数与 `ab56529` 原 `round22_extract.py` / `round29_quote_locate.py` 的对应函数逻辑一致；
   两个校验器（`tools/validate_weighted_tree.py`、`tools/validate_supplementary_agreement.py`）检查项、顺序、消息、退出码不变。自己用 `tests/_baseline_harness.py` 或直接对照复现一次。
2. **CLI 变化**：加权树校验器从"写死默认路径"改为**必填 `--tree`**（该树在注册表里没有登记键）；agreement 校验器改从注册表 `supplementary.cs408_multisource.files` 取路径。
   判断：日常使用会不会因此坏掉（例如有人照 README 旧用法运行）；README / 模块地图 / 其它文档里有没有还写着旧命令或旧文件名的地方（`git grep` 旧文件名）。
3. **依赖方向**：活动 `tools/` 顶层与 `ky/` 没有任何 import 指向 `tools/archive/`；归档脚本之间互相 import 可以接受。归档脚本改了 import 后还能按原方式加载（不要求能重跑出结果）。
4. `tools/README.md` 目录与 `tests/test_tools_catalog.py` 一致；写死路径只保留在归档 / 迁移脚本，且 README 注明。
5. 三个测试文件只改了 import / 调用方式，断言没改（逐文件核对 diff）。

## 规则

只跑与结论直接相关的单个模块或单条命令，**不跑全量**；复现用系统临时目录。结论 PASS / FAIL，分"必须改 / 建议改 / 不改"。

## 报告

`review/rounds/round-214-tools-rounds-archive-review-sol61.md`。
