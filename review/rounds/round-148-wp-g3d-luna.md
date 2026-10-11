# WP-G3d：校验器拆分报告

## 放置与改动范围

只拆分了 `tools/verify_408_index.py` 的 `verify`、`tools/verify_tree.py` 的 `main`，新增固定基线对照测试 `tests/contract/test_index_tree_verifiers_split_baseline.py`，并新增本报告。没有改公开接口、CLI 参数、校验文字、退出码或其他函数；没有写入仓库数据，也没有联网。

对照基线固定为 `ec832c7`。测试用 `git show ec832c7:tools/verify_408_index.py` 和 `git show ec832c7:tools/verify_tree.py` 取旧版，并断言旧 `verify` 大于 300 行、旧 `verify_tree.main` 大于 120 行。

## 拆分函数

行数按当前函数定义首尾行计算。

### `verify_408_index.py`

| 函数 | 行数 | 职责 |
|---|---:|---|
| `_verify_index_header` | 22 | 文件顶层字段、schema 与登记主体/年份检查 |
| `_verify_provenance_shape` | 14 | provenance 字段与来源记录形状检查 |
| `_verify_coverage_shape` | 6 | 答案来源覆盖字段检查 |
| `_verify_entry_identity` | 31 | 题号、主体、年份、题号编号对应关系检查 |
| `_verify_entry_values` | 24 | 分值、题型、答案及知识点字段检查 |
| `_verify_entry_weights` | 46 | 知识点权重、归一化与主知识点一致性检查 |
| `_verify_entry_assignment_status` | 32 | 知识点状态与 ID/权重一致性检查 |
| `_verify_entry_sources` | 13 | 答案来源记录检查 |
| `_verify_entry_locator` | 11 | 定位器与页/行字段检查 |
| `_verify_entry` | 16 | 按原顺序汇总单题各段检查 |
| `_verify_free_text_fields` | 9 | 顶层自由文本字段类型检查 |
| `_verify_totals` | 26 | 连续编号、题目数与分值合计检查 |
| `_verify_answer_coverage` | 19 | 可回答题目计数、选择题答案及大题答案检查 |
| `_verify_registered_provenance` | 31 | ledger 来源、文件哈希与题目定位哈希检查 |
| `_verify_calibration` | 15 | 未校准时的知识点及官方答案声明检查 |
| `verify` | 39 | 按旧顺序组织全部检查并返回问题列表 |

### `verify_tree.py`

| 函数 | 行数 | 职责 |
|---|---:|---|
| `_parse_args` | 10 | 解析原 CLI 参数 |
| `_load_tree_context` | 13 | 加载 workspace、树主体、grammar 与来源根目录 |
| `_load_tree_points` | 2 | 通过知识点契约加载树 |
| `_check_source_hash` | 19 | 校验来源存在性与 SHA-256，并按原规则填充缓存 |
| `_check_quote_ref` | 10 | 检查引用是否存在并记录未解析项 |
| `_check_sources` | 18 | 按原逐来源顺序调用哈希与引用检查并汇总 |
| `_print_source_summary` | 3 | 输出来源文件/哈希统计 |
| `_print_failures` | 4 | 按原格式输出失败项 |
| `_report_source_failures` | 5 | 输出来源阶段失败并决定是否提前退出 |
| `_report_quote_refs` | 8 | 输出引用检查结果并决定是否提前退出 |
| `_check_structure` | 22 | 检查重复 ID、命名空间、语法与结构规则 |
| `_check_provenance` | 10 | 收集证据违规和状态提示 |
| `_check_required_scopes` | 8 | 输出结构计数并校验必需 scope |
| `main` | 40 | 按原阶段顺序组织契约、来源、引用、结构及最终输出 |

## 固定基线变体覆盖

- 408 索引：以 workspace 登记且纸面形状声明答案读取器的索引为种子，生成合法原样 1 个、单项错误 12 个（顶层/schema、provenance、coverage、题目 identity、字段值、weights、assignment、answer sources、locator、自由文本、合计、calibration），以及不冲突的跨段两两组合 66 个；合计 **79 个**。新旧 `verify` 的返回值（UTF-8 序列化字节）、异常类型/消息、stdout、stderr 逐项比较。
- 知识树：动态读取 workspace 登记的三棵有效树。每棵包含原样及来源哈希不符、`quote_ref` 不存在、契约错误、结构错误、`--require-scopes` 缺项 5 个变体；共 **18 个输入**。新旧 CLI 对比 `(退出码, stdout, stderr)` 字节。
- 本次资源均可用，测试未因缺少原始资料跳过。

## 撤修改验证

将 `verify` 中 `_verify_free_text_fields` 与 `_verify_totals` 两次调用对调后，实际执行：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; py -3.12 -m unittest tests.contract.test_index_tree_verifiers_split_baseline
```

结果为 `FAILED (failures=4)`：`cross-coverage-free-text`、`cross-identity-free-text`、`cross-values-free-text`、`cross-free-text-totals` 的问题列表次序与固定基线不同。随后已恢复调用顺序，并重跑验收模块通过。

## 验收与实跑

指定验收命令：

```text
py -3.12 -m unittest tests.contract.test_index_tree_verifiers_split_baseline tests.contract.test_exam_index_port tests.test_exam_index tests.contract.test_knowledge_tree_port tests.test_tools_catalog
```

结果：`Ran 35 tests in 29.666s`，`OK`。

固定提交的真实 CLI 对照与任务书指定的两条实跑结果：

| 命令 | `ec832c7` 对照 | 结果 |
|---|---|---|
| `py -3.12 tools/verify_408_index.py --workspace kaoyan.workspace.yaml` | 退出码、stdout、stderr 完全相同；stdout 314 字节，stderr 0 字节 | 退出码 0，所有登记索引均为 `OK`，最终输出 `ALL INDEX FILES VERIFIED` |
| `py -3.12 tools/verify_tree.py data/structured_materials/math1/knowledge_tree.yaml --workspace kaoyan.workspace.yaml` | 退出码、stdout、stderr 完全相同；stdout 376 字节，stderr 0 字节 | 退出码 0，契约、哈希、`quote_ref`、结构检查通过，最终输出 `ALL CHECKS PASSED` |

另外，`py -3.12 -m py_compile` 覆盖两个工具与新增测试通过；`git diff --check` 无输出。对三个本轮编辑文件执行 `rg -n '\?\?\?'` 未发现连续问号。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）

## 建议

拆分后的阶段入口与固定提交字节对照已覆盖当前校验路径。后续若新增校验段，建议沿用“单段错误 + 跨段错误组合”的对照方式，避免只测单段而漏掉汇总顺序变化。
