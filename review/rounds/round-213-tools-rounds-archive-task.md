# 任务书：技术债包 C —— `tools/` 轮次脚本归档与写死路径（P2-1 / P2-2，窗口 `luna-b`，新会话）

先读 `AGENTS.md`（最高原则 D7、"迁移 / 重构不得改变输出"第 11–13 / 12a 条、已知缺陷第 8 条）、`docs/技术债与整改清单.md` 的 P2-1、P2-2、§9、
`docs/阶段2.5-接缝收口.md` §D2 规则 4（"一次性轮次脚本归档而不是修；写死路径分模块迁移"）、`tools/README.md`（脚本目录与状态）。

## 现状

活动目录里还有 6 个 `roundNN_*`：`round22_extract.py`、`round24_build_weighted_tree.py`、`round29_build_tree_split.py`、`round29_quote_locate.py`（均为
`pinned_reproducer`，固定输入的历史重放），以及 `round24_validate_weighted_tree.py`、`round29_validate_agreement.py`（`validation`，校验**当前登记**的
`knowledge_tree_weighted.yaml` 与补充树 / agreement 附表，决策者 2026-09-29 裁定保持 `validation`）。依赖图：
- `round24_validate_weighted_tree.py`、`round29_quote_locate.py`、`round24_build_weighted_tree.py` 从 `round22_extract` import 提取函数（`extract_2022`、`key` 等）；
  `tools/archive/round22_format.py`、`round22_verify.py` 也 import 它（经 `sys.path.insert(..., "tools")`）。
- `round29_build_tree_split.py` import `round24_build_weighted_tree`、`round29_quote_locate`。
- 测试：`tests/test_round24_weighted_tree.py`、`tests/test_round29_quote_locate.py`、`tests/test_round29_tree_split.py` import 这些模块。
写死路径：`round22_extract.py:20`、`round24_build_weighted_tree.py:60,63`（`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\...`），
`tools/archive/round22_*`、`tools/migrations/register_round2_sources.py:365`。

## 要做

1. **按功能命名、活动代码不依赖归档**：
   - 把被多方复用的**库函数**（`round22_extract` 的提取 / 规范化函数、`round29_quote_locate` 的 `build_keymap` / `locate_quote` 等）移到按功能命名的活动模块
     （例如 `tools/cs408_outline_extract.py`、`tools/cs408_quote_locate.py`——名字你定，说明理由），模块头写 M 编号与用途。
   - 两个 `validation` 校验器改为按功能命名（例如 `tools/validate_weighted_tree.py`、`tools/validate_supplementary_agreement.py`），改为从上述活动模块 import。
   - 4 个 `pinned_reproducer` 的**脚本本体**移到 `tools/archive/`（名字保留 `roundNN_`：归档记的就是历史轮次），改为 import 活动库模块；
     `tools/archive/round22_format.py`、`round22_verify.py` 同步改 import。**活动代码（`tools/` 顶层与 `ky/`）不得 import `tools/archive/` 下任何东西。**
   - 不留兼容别名（不要在旧文件名处放转发 stub）。
2. **写死路径**：活动模块与两个校验器里的写死路径改为从注册表 / `data/materials.yaml` 台账解析（`raw_root` 下的登记路径），或改为必填 CLI 参数——
   以现有同类工具的做法为准，报告说明选择。归档脚本里的写死路径**保留原样**（它们是历史重放，不可重跑），在 `tools/README.md` 该行注明。
   `tools/migrations/register_round2_sources.py` 同理只在 README 注明，不改。
3. **测试与目录**：3 个测试文件改 import；`tools/README.md` 目录表同步（新文件名、状态、依赖图一节）；`tests/test_tools_catalog.py` 必须通过。
   `tests/test_cs408_lecture_pipeline.py:89` 从固定提交读历史源码的断言确认仍成立（报告写明）。
4. **输出不变的证明**：两个校验器与被移动的库函数，在同一输入上新旧输出逐字节一致。用 `tests/_baseline_harness.py`（固定到本轮开始时的 master 哈希，派发时为 **`BASELINE`**，见文末）
   写一次性对照，结果写进报告即可（清单 §9：迁移对照已退役，不新增常驻对照测试）；需要外部资料的场景照 `tests/_resources.require_path` 跳过并写明。

## 不做的

不改 `ky/`；不改任何校验规则、输出文字、退出码；不修归档脚本的逻辑；不动其它 `tools/` 脚本；不跑全量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_tools_catalog tests.test_round24_weighted_tree tests.test_round29_quote_locate tests.test_round29_tree_split tests.test_cs408_lecture_pipeline tests.test_tool_exit_paths
```

另跑：`git grep -n "roundNN\|round2[249]_" -- tools/*.py ky` 只应命中归档说明或无命中（贴结果）；`git grep -n "tools/archive\|archive import" -- tools/*.py ky` 无活动代码命中。

## 报告

`review/rounds/round-213-tools-rounds-archive-luna.md`：新旧文件对应表、依赖图（改后）、写死路径处理清单、README 改动、输出对照方法与结果、验收输出原文。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文只用 `apply_patch`，写完查 `???`。

---

**BASELINE = `ab56529`**（包 B 提交后的 master）。
