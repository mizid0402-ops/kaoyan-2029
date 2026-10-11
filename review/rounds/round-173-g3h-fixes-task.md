# 任务书：WP-G3h 返工 —— sol 172 的 M1 / M2（窗口 `luna-a` 续做）

你在第 170 轮交付的 WP-G3h 已作为 `4b0bc93` 提交（全量 911 项 OK），但 sol 第 172 轮判 **FAIL**，
两条"必须改"留到本轮。先读 `review/rounds/round-172-g3h-tools-review-codex.md` 全文，再读
`AGENTS.md`（"迁移 / 重构不得改变输出"第 11–13 条与 12a、"已知缺陷清单"第 8 条）。

本轮没有其他窗口在改 `tools/` 与 `tests/`；你只改下面点名的文件。

## 第一部分：G3h-M1 —— 对照测试要能在干净归档里独立运行

`review/408知识点树与真题` 是 gitignore 的登记产物目录（注册表 `products.cs408_lecture_workspace`
指向它），`git archive` 不带它。`tests/test_tools_split_baseline.py` 里两个场景依赖它：

- `test_html_extraction_matches_products_and_argument_failure`：输出虽重定向到临时目录，
  仍先走原 `_configure_workspace`，要求登记目录存在；
- `test_verifier_and_report_tools_match_fixed_baseline`：`verify_408_question_extraction.py`
  直接读登记目录下的 `questions/questions_index.json`。

在干净归档里这两个场景的新旧版本都抛 traceback，三元组因行号不同而失败
（`Ran 5 tests ... FAILED (failures=2, skipped=1)`）。**缺产物触发的 traceback 对照不是行为对照。**

要求：

1. **HTML 提取场景**：在临时目录里放一份临时注册表（或临时产物根），使新旧脚本都能在
   **不依赖仓库登记产物**的情况下走成功路径，并逐文件比较产出原始字节 + `(退出码, stdout, stderr)`。
   仍依赖的**输入**（原始 HTML 等，若为 gitignore 的原始资料）用 `tests._resources.require_path`
   标明缺失路径与恢复来源并跳过；参数失败那一支应当不依赖任何外部资源，要能在干净归档里跑。
2. **验证器场景**：`verify_408_question_extraction.py` 的成功路径要么在临时目录里构造一份
   它能验证的最小产物（首选；要真能走到它的各段检查，而不是一进门就失败），要么用
   `require_path` 对登记产物目录标明"缺什么、从哪恢复"（例如"运行 `tools/extract_408_questions_from_html.py` 生成"）并**只跳过这一个子场景**——
   同一测试方法里其他不依赖登记产物的脚本对照（netem 等）不得因此被一并跳过，必要时拆成独立测试方法。
3. 检查整份 `tests/test_tools_split_baseline.py`：还有没有别的场景读 gitignore 的路径而没有
   `require_path`。有就同样处理，报告里列出。
4. **自证**：照 sol 172 的做法，用 `git archive HEAD` 导出到系统临时目录（只补 sol 补过的
   原始资料与空 `products` 根，**不**补 `review/408知识点树与真题`），设
   `GIT_DIR=<主库 .git>`、`PYTHONDONTWRITEBYTECODE=1`，在归档里跑
   `py -3.12 -m unittest tests.test_tools_split_baseline`，结果不得有失败；再在主仓库跑一次。
   报告里贴两次的 `Ran …` 行和跳过原因原文。

不改 `tools/` 下任何脚本来"迁就"测试（第一部分是纯测试改动）。

## 第二部分：G3h-M2 —— 补拆两支 `validation` 校验器

决策者裁定：`tools/README.md` 把 `round24_validate_weighted_tree.py` 与
`round29_validate_agreement.py` 列为 **`validation`**，二者校验的都是**当前登记的数据文件**
（`data/structured_materials/cs408/knowledge_tree_weighted.yaml`；`knowledge_tree_multisource.yaml`
与 agreement 附表），**分类不改**，按 G3h 同一规则补拆：

- `tools/round24_validate_weighted_tree.py::validate`（76 行）
- `tools/round29_validate_agreement.py::validate`（78 行）

拆成有名字的辅助，每步一件事（例如 schema 检查 / 主表与附表互相包含 / 来源支持重算比对 /
来源计数），`validate` 只做编排。保留两文件模块头 docstring 所写的"独立校验器、不 import
构建脚本内部状态"的设计；**不改**检查项、检查顺序、错误消息文字、返回值形状、退出码。

再对 README 状态为 `active` / `validation` / `acquisition` 的全部脚本做一次 AST 扫描
（`end_lineno - lineno + 1`），报告里给出扫描脚本与结果：应当**没有任何函数超过 60 行**。

### 对照测试

- 基线**固定 `58f44bc`**（本轮改动前的 master），用 `git show 58f44bc:tools/<文件>` 取旧版，
  并 AST 断言取到的 `validate` 确实是拆分前的长函数（≥ 70 行）。**不得用 `HEAD`**（第 12a 条）。
- 两支校验器各覆盖**成功路径**（登记数据）与**至少一条失败路径**（在临时副本里改坏一处，
  使某一段检查报错），比较新旧版本 `(退出码, stdout, stderr)` 原始字节；若函数有返回值
  （错误列表等），也比较返回值。失败路径要**真的触发**你声称的那段检查——在测试里断言
  输出里出现该段的错误消息，而不仅是"两版相同"。
- round24 的校验需要本地来源缓存（见 `tests/test_round24_weighted_tree.py` 的 `require_path` 用法）：
  缺的照同样方式跳过并写明缺什么；不依赖外部资源的失败路径要能在干净归档里跑。
- 对照放进 `tests/test_tools_split_baseline.py` 新增一个测试类（与 G3h 的 `24371ee` 基线分开，
  各自一个常量），或新文件 `tests/test_validators_split_baseline.py`——选前者还是后者你定，报告说明理由。
- **已有测试不许改断言**：`tests/test_round24_weighted_tree.py`、`tests/test_round29_tree_split.py`、
  `tests/test_tools_catalog.py` 必须原样通过。

### 撤实现验证

定点变异：改掉某个新拆出辅助的返回值，或调换两段检查的顺序；设 `PYTHONDONTWRITEBYTECODE=1`
并清 `__pycache__`；**报告写实际命令与实际结果**（哪条测试变红、红在哪一行断言），然后恢复。

## 不做的

- 不修 sol 172"建议改 S1"里的两条旧异常路径（`probe_exam_pdf.py` 连接失败 traceback、
  `extract_exam_skeleton.py --json <仓库外路径>`）——另包处理。
- 不改 `tools/README.md` 的分类，不改任何输出文字、字段名、错误消息、退出码、默认路径。
- 不动 `pinned_reproducer` / `migration` / `archived` / `retired` 脚本；不动 `ky/`。
- 不跑全量测试。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_tools_split_baseline tests.test_tools_catalog tests.test_round24_weighted_tree tests.test_round29_tree_split
```

若新建了 `tests/test_validators_split_baseline.py`，一并加进命令。另加第一部分第 4 条的干净归档复跑。

## 报告

`review/rounds/round-173-g3h-fixes-luna.md`，分两节（M1 / M2）。每节写：改了什么、
对照覆盖了什么（场景名 → 成功 / 失败 / 跳过及原因）、**撤实现验证的实际命令与结果**、验收输出原文。
M2 节另附 AST 扫描脚本与结果。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。
含中文的文件**只用 `apply_patch` 编辑**，写完查 `???`。
