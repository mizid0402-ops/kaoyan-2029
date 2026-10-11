# 任务书：WP-G3c 收尾 + WP-G3h `tools/` 大函数拆分（窗口 `luna-a` 续做）

你刚交付 WP-G3c 余项（`review/rounds/round-166-wp-g3c-remainder-luna.md`），
sol 第 167 轮判 **PASS**（`review/rounds/round-167-g3c-remainder-review-codex.md`，
只提了一条建议）。本轮两部分，**分两节写报告**。

先读 `AGENTS.md`（"最高原则"、"迁移 / 重构不得改变输出"）、
`review/rounds/round-167-g3c-remainder-review-codex.md`（尤其"建议改 S1"）。

另外两个窗口在改别的目录，**不要碰**：`luna-b` 在 `ky/schedule/`、`luna-c` 在
`ky/storage/`、`ky/ledger/`、`ky/freeze/`。你只改 `ky/__main__.py` 和 `tools/` 下的活跃工具。

## 第一部分：sol 167 S1（只改 `ky/__main__.py`）

`_snapshot_build` 只把参数原样转发给 `build_snapshot`，自己不做组装、校验或决策，属于
D7 与第 150 轮 sol 都反对的"纯转发辅助函数"。**去掉这个中转**：在 `snapshot_main` 里直接调用
`build_snapshot`（`snapshot_main` 变长约 6 行，仍在 60 行以内）。

- 如果新增的对照测试里出现了 `_snapshot_build` 的名字，同步更新。
- **输出与退出码逐字节不变**，由 `CliG3cRemainderSplitBaselineTests` 证明（必须仍然全绿）。

## 第二部分：WP-G3h — `tools/` 活跃工具的大函数拆分

扫 `tools/` 下**下列三类**脚本，把超过约 60 行的函数拆成有名字的辅助（每步一件事）：

- `active`：`aggregate_topic_weights.py`、`apply_knowledge_weights.py`、`render_weight_manual.py`、
  `classify_questions.py`、`daily_words.py`、`build_408_deck_scaffold.py`、`extract_cs408_bundle.py`、
  `extract_408_question_text.py`、`extract_408_questions_from_html.py`、`import_netem_source.py`
- `validation`：`verify_408_index.py`、`verify_tree.py`、`tree_source_support.py`、
  `verify_eng1_vocabulary.py`、`verify_netem_source.py`、`netem_cross_validate.py`、
  `verify_408_question_extraction.py`、`probe_outline.py`、`probe_pdf_text.py`、
  `extract_exam_skeleton.py`、`list_tree_vocab.py`
- `acquisition`：`fetch_evidence.py`、`fetch_all_from_ledger.py`、`probe_exam_pdf.py`、
  `render_pdf_pages.py`、`render_staged_page.py`

`tools/README.md` 的表格把每个脚本的状态写清楚了（`active` / `validation` / `acquisition` /
`pinned_reproducer` / `migration` / `archived` / `retired`）——**照它判断**。
已知超过 60 行的至少有：`verify_eng1_vocabulary.py::verify_database`（132）、
`extract_exam_skeleton.py::main`（84）、`verify_netem_source.py::verify_database`（83）、
`probe_exam_pdf.py::main`（81）、`netem_cross_validate.py::main`（71）、
`verify_408_question_extraction.py::_verify_records`（69）、
`render_weight_manual.py::section_cs408`（66）、
`extract_408_questions_from_html.py::_extract_question`（62）与 `_build_extraction_report`（62）；
其余自己扫一遍，报告里给完整清单。

**不拆**：`pinned_reproducer`（`round*_*.py`、`build_eng1_vocabulary.py`）、`migration`、
`archived`、`retired` —— 这些是历史重放脚本，输出带时间戳、依赖固定输入，
拆分收益低而对照风险高。在报告里写一句你确认过的理由即可。

重点提醒：
- `extract_408_questions_from_html.py`、`build_408_deck_scaffold.py` 等 M21 脚本的
  **正文小节、覆盖表、"无命中不等于不考"提示**都是用户可见输出，第 49 轮事故就出在这里
  （`AGENTS.md` 第 11–13 条）。一个字符都不能变。
- `render_weight_manual.py` 生成的说明书由 `tools/README.md` 登记，正文照原样输出。
- 拆 `main(argv)` 时，参数解析 / 读输入 / 计算 / 写产物 / 打印各自成函数。

## 输出必须逐字节不变

两个部分都是**纯重构**。

- 基线**固定 `24371ee`**（本批改动前的 master），用 `git show 24371ee:<文件>` 取旧版并
  **断言取到的是拆分前的长实现**。`AGENTS.md` 第 12a 条：固定提交哈希，**不得用 `HEAD`**。
- `tools/` 这批**至少为每个你改过的脚本写一个固定基线对照**：`active` 里能产出文件的
  （`render_weight_manual.py`、`build_408_deck_scaffold.py`、`extract_cs408_bundle.py`、
  `extract_408_question_text.py`、`extract_408_questions_from_html.py`）比较
  **产出的每个文件原始字节 + `(退出码, stdout, stderr)`**；只读的（`validation` /
  `acquisition`）比较 `(退出码, stdout, stderr)`，并为每个脚本覆盖成功路径与一条失败路径。
  新增 `tests/test_tools_split_baseline.py`（或按现有 `tests/test_*_split_baseline.py` 的组织方式）。
  需要外部原始资料的用例照 `tests/_resources.require_path` 的做法跳过并写明缺什么。
- **已有测试不许改断言**：`tests/test_tools_catalog.py`、
  `tests/test_deck_scaffold_split_baseline.py`、
  `tests/contract/test_index_tree_verifiers_split_baseline.py` 必须原样通过。
- 撤实现验证：定点变异（改掉某个新拆出的辅助的返回值，或调换两步顺序），
  设 `PYTHONDONTWRITEBYTECODE=1` 并清 `__pycache__`，**报告写实际命令与实际结果**。

## 不做的

- 不改任何输出文字、字段名、错误消息、退出码。
- 不修 bug、不新增功能、不改默认路径。
- 不动 `pinned_reproducer` / `migration` / `archived` / `retired` 脚本。
- 不动 `ky/` 下除 `ky/__main__.py` 之外的文件。
- 不跑全量测试。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_cli tests.test_cli_split_baseline tests.test_tools_catalog tests.test_tools_split_baseline tests.test_deck_scaffold_split_baseline tests.contract.test_index_tree_verifiers_split_baseline
```

外加你改过的每个脚本相关的已有测试模块（自己在 `tests/` 里找，报告里列出实际命令）。

## 报告

`review/rounds/round-170-wp-g3h-tools-luna.md`：**分两节**（第一部分 S1 / 第二部分 G3h）。
每节写：拆分落点（每个函数拆出哪些辅助、各自职责一句话）、对照测试覆盖了什么、
**撤实现验证实际跑了什么命令、实际结果**、验收输出原文；第二部分另写"未拆的脚本及理由"。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。
含中文的文件**只用 `apply_patch` 编辑**，写完查 `???`。
