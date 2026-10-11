# 技术债包 D：`ky/` 规格引用、exam 包与行宽

基线提交：`f52b8f6`。本轮只修改 `ky/` 与本报告；未提交。工作区中既有的
`round-200-baseline-harness-task.md`、`round-201-ky-headers-lines-task.md` 保持原样。
并行窗口 `luna-a` 的 `tests/` 修改（`test_availability_port.py`、
`test_day_budget_port.py`、`test_freeze_port.py`、`test_planner_port.py`、
`_baseline_harness.py`、`_fixtures.py`、`test_baseline_harness.py`）未触碰，也未纳入本包。

## 1. 规格反向引用（P1-4）

- `ky/models.py`：增加 M8 配置规格引用 `contracts/config.md`，列出配置接口。
- `ky/ledger/material.py`：增加 M2 的 `contracts/ledger.md` 引用。
- `ky/ledger/citations.py`：增加 M3 的 `contracts/citation_gate.md` 引用。
- `ky/storage/day_plan_store.py`：在原规格列表中补入 `contracts/day_plan_store.md`。
- `ky/schedule/review_clip.py`：在原有 `contracts/route_plan.md` 引用旁补入
  `contracts/review_clip.md`。

按 `git grep -l "<规格名>.md" -- ky` 逐份核对的结果（25/25 有命中）：

| 规格 | `ky/` 命中文件 |
|---|---|
| availability.md | `ky/availability/__init__.py`, `ky/availability/port.py`, `ky/schedule/budget.py` |
| check_questions.md | `ky/review/check_questions.py` |
| citation_gate.md | `ky/ledger/citations.py` |
| config.md | `ky/models.py` |
| day_plan_store.md | `ky/storage/day_plan_store.py` |
| exam_index.md | `ky/projection/__init__.py` |
| freeze.md | `ky/freeze/__init__.py`, `ky/freeze/port.py`, `ky/freeze/resume.py`, `ky/storage/day_plan_store.py` |
| knowledge_tree.md | `ky/knowledge/hierarchy.py`, `ky/knowledge/knowledge_point.py` |
| learning_state_projection.md | `ky/projection/__init__.py`, `ky/projection/learning_state.py` |
| ledger.md | `ky/ledger/material.py` |
| material_restore.md | `ky/acquisition/__init__.py`, `ky/acquisition/ledger_restore.py` |
| paper_shape.md | `ky/exam/paper_shape.py` |
| planner_port.md | `ky/planner/port.py`, `ky/storage/day_plan_store.py` |
| projection.md | `ky/projection/__init__.py`, `ky/projection/learning_state.py` |
| projection_status.md | `ky/projection/status.py` |
| review_clip.md | `ky/schedule/review_clip.py` |
| review_progress.md | `ky/schedule/completion.py`, `ky/storage/day_plan_store.py` |
| route_plan.md | `ky/__main__.py`, `ky/schedule/budget.py`, `ky/schedule/planning.py`, `ky/schedule/review_clip.py`, `ky/storage/route_store.py` |
| state_snapshot.md | `ky/schedule/state_snapshot.py`, `ky/storage/day_plan_store.py` |
| state_sources.md | `ky/availability/port.py`, `ky/storage/day_plan_store.py`, `ky/storage/review_shards.py`, `ky/storage/route_store.py` |
| syllabus_mapping.md | `ky/knowledge/syllabus_mapping.py` |
| syllabus_migration.md | `ky/review/syllabus_migration.py` |
| topic_weights.md | `ky/exam/topic_weights.py` |
| vocabulary.md | `ky/schedule/vocab_channel.py` |
| workspace.md | `ky/planner/port.py`, `ky/workspace.py` |

## 2. `ky/exam` 包（P0-5）

新增 `ky/exam/__init__.py`，只含模块 docstring，没有 re-export。其它包并不一致：
`ky/availability`、`ky/freeze`、`ky/ledger`、`ky/knowledge`、`ky/projection`、
`ky/schedule`、`ky/storage` 存在 re-export；`ky/acquisition`、`ky/contracts`、
`ky/planner`、`ky/review` 只含说明或为空。因此本文件沿用仅说明接口的形式。

全文：

```python
"""M5′ paper shape and M6 topic weights.

See ``contracts/paper_shape.md`` and ``contracts/topic_weights.md``.
Public interfaces are provided by :mod:`ky.exam.paper_shape` and
:mod:`ky.exam.topic_weights`.
"""
```

## 3. 超长行（P2-4）

修改文件：`ky/__main__.py`、`ky/knowledge/knowledge_point.py`、`ky/models.py`、
`ky/projection/serve.py`、`ky/schedule/completion.py`、`ky/schedule/monthly_close.py`、
`ky/storage/day_plan_store.py`、`ky/storage/review_shards.py`、`ky/workspace.py`。
全部为折行、括号内排版、字面量分项或相邻字符串拼接。

`ky/` 中超过 100 字符的行：55 → 0。`ky/__main__.py` 的 usage 示例和
`MonthClose.utilisation` 的 docstring 值另与固定基线核对，均未改变。

## 4. 固定基线 AST 检查

检查脚本位于系统临时目录 `C:\Users\Lenovo\AppData\Local\Temp\round201_ast_check.py`，
基线固定为 `f52b8f6`。脚本移除模块、类和函数 docstring 后比较 AST；新文件要求除
docstring 外没有 AST 节点。

脚本全文：

```python
import ast
import subprocess
import sys
from pathlib import Path

BASELINE = "f52b8f6"
ROOT = Path.cwd()


class RemoveDocstrings(ast.NodeTransformer):
    def _strip(self, node):
        self.generic_visit(node)
        if node.body and isinstance(node.body[0], ast.Expr):
            value = node.body[0].value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                node.body = node.body[1:]
        return node

    visit_Module = _strip
    visit_ClassDef = _strip
    visit_FunctionDef = _strip
    visit_AsyncFunctionDef = _strip


def normalized(source, filename):
    tree = ast.parse(source, filename=filename)
    return ast.dump(RemoveDocstrings().visit(tree), include_attributes=False)


changed = subprocess.run(
    ["git", "status", "--porcelain", "--", "ky"],
    check=True,
    capture_output=True,
    text=True,
).stdout.splitlines()
paths = sorted(line[3:] for line in changed if line[3:].endswith(".py"))
failed = False
for relative in paths:
    current = (ROOT / relative).read_text(encoding="utf-8")
    previous = subprocess.run(
        ["git", "show", f"{BASELINE}:{relative}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if previous.returncode == 0:
        same = normalized(previous.stdout, relative) == normalized(current, relative)
        status = "PASS" if same else "FAIL"
    else:
        same = normalized(current, relative) == ast.dump(
            ast.Module(body=[], type_ignores=[]), include_attributes=False
        )
        status = "PASS (new file: docstring only)" if same else "FAIL (new file has code)"
    print(f"{status}: {relative}")
    if not same:
        failed = True
sys.exit(1 if failed else 0)
```

逐文件结果：

```text
PASS: ky/__main__.py
PASS (new file: docstring only): ky/exam/__init__.py
PASS: ky/knowledge/knowledge_point.py
PASS: ky/ledger/citations.py
PASS: ky/ledger/material.py
PASS: ky/models.py
PASS: ky/projection/serve.py
PASS: ky/schedule/completion.py
PASS: ky/schedule/monthly_close.py
PASS: ky/schedule/review_clip.py
PASS: ky/storage/day_plan_store.py
PASS: ky/storage/review_shards.py
PASS: ky/workspace.py
```

乱码检查命令 `git grep -c '???' -- ky`：无输出，退出码 1（无匹配）。

## 5. 验收

实际命令（仓库中的模块名均存在）：

```text
py -3.12 -m unittest tests.contract.test_config_port tests.contract.test_ledger_port tests.contract.test_day_plan_store_port tests.contract.test_review_clip_port tests.contract.test_citation_gate_port tests.contract.test_paper_shape_port tests.contract.test_topic_weights_port tests.contract.test_knowledge_tree_port tests.contract.test_workspace tests.contract.test_review_progress_port tests.test_projection_service tests.test_cli
```

原始输出：

```text
----------------------------------------------------------------------
Ran 218 tests in 32.110s

OK (skipped=1)
national.json: write=0 unchanged=0 missing=1 rejected=0 single_node=0 spread=0
   - missing from topic_weights.json: cs408-2023-01
school.json: write=1 unchanged=0 missing=0 rejected=0 single_node=1 spread=0

TOTAL write=1 unchanged=0 missing=1 rejected=0 single_node=1 spread=0
```

注：进度点由 unittest 写至 stderr，运行器按多个片段转发；上方记录最终汇总及
验收命令产生的其余原始 stdout 内容。命令退出码为 0。
全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。
