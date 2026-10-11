# 任务书：技术债包 D —— `ky/` 规格反向引用、`ky/exam` 包、超长行（P1-4 / P0-5 / P2-4，窗口 `luna-c`，新会话）

先读 `AGENTS.md`（最高原则 D7：模块头写明模块编号、规格、对外接口；行宽 ≤ 100；"迁移 / 重构不得改变输出"），
再读 `docs/技术债与整改清单.md` 的 P0-5、P1-4、P2-4 与 §9、`docs/模块地图.md`。

另一个窗口 `luna-a` 在改 `tests/`（对照测试收敛），**不要碰 `tests/`、`tools/`**。本包**只改 `ky/`**，而且**行为逐字节不变**。

## 要改

1. **P1-4 规格反向引用**：`contracts/config.md`、`contracts/ledger.md`、`contracts/day_plan_store.md`、`contracts/review_clip.md`、
   `contracts/citation_gate.md` 在 `ky/` 里没有任何模块头提到它们。按 `docs/模块地图.md` 找到各自的实现模块
   （例如 `config.md` → `ky/models.py` 的配置部分，`day_plan_store.md` → `ky/storage/day_plan_store.py`，`review_clip.md` → `ky/schedule/review_clip.py`，
   `ledger.md` / `citation_gate.md` → `ky/ledger/` 下的模块——以模块地图为准），在模块头 docstring 里补上规格引用，
   照同文件已有写法。验收：`git grep -l "<名>.md" -- ky` 对 `contracts/` 下**全部** `*.md` 都至少有一处命中（报告贴出逐份结果；
   若某份规格确实没有 `ky/` 实现——例如只约束 `tools/` 或数据文件——写明，不硬塞）。
2. **P0-5 `ky/exam/__init__.py`**：`ky/exam/` 是 `ky` 里唯一缺 `__init__.py` 的子包（现在靠命名空间包）。补一个，只写模块头 docstring
   （模块编号 M5′ / M6、对应规格 `contracts/paper_shape.md`、`contracts/topic_weights.md`、对外接口），照其它子包 `__init__.py` 的写法；
   **不要**在里面 re-export 新名字，除非其它子包都这么做（以现有子包为准，报告说明）。
3. **P2-4 超长行**：`ky/` 下超过 100 字符的行（当前 55 行，集中在 `ky/knowledge/knowledge_point.py`、`ky/storage/review_shards.py`、
   `ky/models.py`、`ky/workspace.py`、`ky/projection/serve.py`、`ky/__main__.py` 第 13 行的文档示例等）全部折到 ≤ 100。
   只做格式：隐式字符串拼接、括号内换行、字面量表按项换行。**不改任何字符串的值、任何表达式的含义。**

## 行为不变的证明（必须）

写一个一次性检查（放系统临时目录，不进仓库）：对本包改动的每个 `.py`，分别解析 `git show HEAD:<文件>` 与当前文件的 AST，
**去掉模块 / 类 / 函数的 docstring 后**比较 `ast.dump(..., include_attributes=False)`，必须完全相同。
（第 1、2 条只动 docstring；第 3 条只动排版——两者在去掉 docstring 的 AST 上都应零差异。）
例外：若折行必须改动字符串拼接方式，隐式拼接在 AST 里会被合并成同一个常量，仍应相同；若出现任何非 docstring 差异，停下来在报告里列出，不要提交那一处。
报告贴出检查脚本全文与逐文件结果；再贴 `git grep -c '???' -- ky` 结果。

## 不做的

不改逻辑、不改输出文字、不改导入；不动 `tests/`、`tools/`、`contracts/`、`data/`；不跑全量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_config_port tests.contract.test_ledger_port tests.contract.test_day_plan_store_port tests.contract.test_review_clip_port tests.contract.test_citation_gate_port tests.contract.test_paper_shape_port tests.contract.test_topic_weights_port tests.contract.test_knowledge_tree_port tests.contract.test_workspace tests.contract.test_review_progress_port tests.test_projection_service tests.test_cli
```

模块名以仓库实际为准（`ls tests/contract` 确认），报告写实际命令。

## 报告

`review/rounds/round-201-ky-headers-lines-luna.md`：每条改了哪些文件、25 份规格的反向引用结果、`ky/exam/__init__.py` 全文、
超长行前后计数、AST 检查脚本与结果、验收输出原文。写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。
不提交。含中文只用 `apply_patch`，写完查 `???`。
