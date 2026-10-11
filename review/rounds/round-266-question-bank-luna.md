# 第 266 轮：M31 改编题库实现报告

## 改动与做法

- `ky/workspace.py` 接受主注册表与本地 overlay 的 `state.question_bank`，作为目录型写入目标；它仍不能通过 `require()` 读取。
- 新增 `ky/question_bank/`：题目 schema 与文件名校验、重复 YAML 键拒绝、题目列表读取、按两位序号追加；发布使用同目录临时文件、重读校验和 `os.link`，旧题不覆盖。取题优先当前知识点，再按最近祖先；每组先取序号最小的未用题，全部用过后取最近使用日期最早的题。
- 新增改编题输入包和 staged submit：输入包包含知识点树路径、目标点及后代的大纲标题、M24 候选元数据和定位，不包含真题题干；无候选时 `basis: syllabus`。提交校验 M19 actor、输入 hash 新鲜度、题库 basis、`based_on` 候选关系及可学节点，然后写入题库。`--dry-run` 不创建题库文件。
- `ky/review/check_questions.py` 增加祖先回退。仅当目标节点自身没有候选时，沿 M4 `tree_parent` 向上，将祖先及其后代映射的权重相加，并返回 `matched_ancestor`；未传参数时原候选映射不变。为遵守 M31 同次读取索引元数据的要求，增加仅供 M31 使用的可选 `include_details` 参数；缺省候选结构保持不变。
- `ky/__main__.py` 增加 `planner-input --kind adapted-questions`、`question-bank submit` 和 `review-questions`。后者使用与 preflight 相同的 M9 选择、M30 `item_level` 和 M13 完成事件；完成事件中的 `question_ref` 用于排除已用真题和安排改编题轮转。
- 新增 `prompts/adapted_questions.md` 与契约测试；在 `tests/contract/test_workspace.py` 增加本地目录登记断言。未改 README、模块地图、交接文档、M9 排序、既有 preflight 输出或个人数据。

## 歧义与选择

- 任务书测试条目末尾写“知识点不是可学叶子拒绝”，但题库规格 §4 明确允许任一可学节点，并要求支持非叶子粗粒度节点；同一测试条目前文也要求非叶子生成。实现按规格执行：允许可学非叶子，拒绝跟踪节点。新增测试覆盖这两种边界。
- 祖先节点存在映射、但其候选都被 `exclude` 排除时，按“第一个有候选的祖先”停止上溯；返回空候选且不报告无真题 fallback。规格将祖先候选被排除后是否继续上溯列为待最终核对，本轮不自行扩展规则。
- `include_details=True` 仅用于输入包装配，从候选同次索引读取里补充题型、分值及 `answer_kind: letter` 时的答案字母；默认 `candidate_check_questions` 仍只返回 M24 原字段。

## 验收

命令：

```text
py -3.12 -m unittest tests.contract.test_question_bank_port tests.contract.test_check_questions_port tests.contract.test_workspace tests.contract.test_planner_port tests.test_cli
```

测试输出原文：

```text
...............................s..............................................
..written: C:/Users/Lenovo/AppData/Local/Temp/tmpwtpfcxr0/human-routes/route--r1.yaml (revision 1, sha256 639d58ce3a9ae3d84f2d8ac9d8c6992cf108233fe1e13c86f53865df0188c573)
....................................
.............................
....
----------------------------------------------------------------------
Ran 149 tests in 92.791s

OK (skipped=1)
written: C:/Users/Lenovo/AppData/Local/Temp/tmpwtpfcxr0/data/routes/route--r1.yaml (revision 1, sha256 8c6b098c2939060156b7c6675e7f570ea6d33a5bc9c60794e4ba92e346b43c8c)
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

`git diff --check` 通过；对本轮涉及的中文文件执行 `rg -n '\?\?\?'`，无匹配；新增文件为 LF 换行。

怀疑受影响但任务未点名的模块：无。M0、M4、M13、M14、M24、M30 均属于任务书列出的接口或实现范围。
