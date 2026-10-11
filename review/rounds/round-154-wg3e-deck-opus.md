# 第 154 轮 WP-G3e 实现报告：拆分 408 讲义脚手架 / 导出脚本（D7）

实现者：opus（worktree `agent-a97a643b4ba13e94a`，分支 `worktree-agent-a97a643b4ba13e94a`，基于 `b43eb1f`）。未提交。

## 1. 改动概要

只做结构拆分，不改 CLI 参数、文字、输出与错误行为；没有兼容别名。两份脚本所有函数现在都 ≤ 60 行、嵌套 ≤ 3 层。

### `tools/build_408_deck_scaffold.py`

| 原函数（行数） | 拆分后（行数） | 说明 |
|---|---|---|
| `_unit_document`（81） | `_unit_document`（20） | 只按原顺序拼装下列五节 |
| | `_unit_header`（29） | 标题、生成注释、补充视图行、单元信息表 |
| | `_unit_children_section`（14） | `## 本单元覆盖的知识条目` 与子条目列表 |
| | `_unit_question_section`（23） | `## 真题定位` 表格，或"无命中不等于不考"提示 |
| | `_unit_lecture_section`（26） | `## 讲解正文` 与 考点提炼 / 原理与推导 / 易错点 / 真题印证（含前 3 题摘录位） |
| | `_unit_practice_section`（3） | `### 练习指向` |
| `_questions_for_unit`（48，**4 层嵌套** for→while→if→if） | `_questions_for_unit`（33） | 按 AGENTS.md "三层以上嵌套时拆" |
| | `_unit_points`（15） | 候选知识点：先前缀匹配，再按 `kp_questions` 顺序追加树后代（顺序保持不变） |
| | `_has_ancestor`（11） | 沿 `parent_id` 上溯，`visited` 防环（与原 while 循环等价） |

### `tools/extract_cs408_bundle.py`

| 原函数（行数） | 拆分后（行数） | 说明 |
|---|---|---|
| `build_bundle`（60） | `build_bundle`（33） | 读取、导出、写表顺序不变 |
| | `_generated_from`（12） | manifest 的 `generated_from` |
| | `_manifest_counts`（13） | manifest 的 `counts` |
| | `_write_manifest`（29） | 组装 manifest（键顺序不变）并写 `manifest.json` |

`view` 参数的类型注解用了 `ky.workspace` 的公开类 `SupplementaryView`（新增一个公开名 import）。

未拆：`_write_coverage`（56 行，嵌套 2 层）低于约 60 行门槛，按"不镀金"保留；其余函数均 ≤ 39 行。
行宽：两份脚本无超过 100 字符的行（按字符计）。`rg '\?\?\?'` 无命中。

## 2. 基线测试 `tests/test_deck_scaffold_split_baseline.py`

- **固定基线**：`BASELINE_COMMIT = "9cb8132"`，用 `git show 9cb8132:tools/…` 取两份旧脚本，不用 `HEAD`（第 12a 条）。
  `setUpClass` 断言取到的确是旧版：旧 `_unit_document` > 70 行；旧 `build_bundle` ≥ 60 行且不存在 `_write_manifest`。
- **同一份输入**：临时目录下建工作区，**逐字节复制真实注册表** `kaoyan.workspace.yaml`，按注册表把补充视图的 tree / agreement、
  该科目的生效知识树与全部登记真题索引复制到同一相对路径，并创建登记的产品目录。输入文件从注册表推导，不写科目 / 年份 / 数量字面量（D5/D6、第 7/8 条）。
  注册表或任一输入缺失时用 `tests._resources.require_path` 跳过并说明原因。
- **运行方式**：旧版与新版都以子进程运行 `脚本 --workspace <临时注册表>`（先 bundle 后 scaffold），`PYTHONPATH` 指向仓库以共用同一 `ky` 包，
  `PYTHONDONTWRITEBYTECODE=1`、去掉 `KY_WORKSPACE`。两侧先后使用**同一路径**的新建工作区（旧版跑完拍快照、删掉、重建再跑新版），因此 stdout 里的输出路径与 manifest 中的相对路径可以直接逐字节比较。
- **比较内容**：两个命令各自的 (退出码, stdout 字节, stderr 字节) 完全相等；工作区内全部文件的路径集合相等，且每个文件原始字节相等（含 `tree_flat.json/csv`、`tree_outline.md`、`question_index.csv`、`kp_to_questions.csv`、`coverage.md`、`manifest.json` 与全部 `deck/*.md`，也含未被改动的输入副本）。没有任何归一化或放过的差异。
- **防"基线本身是空的"**：断言旧版输出里每个讲解单元都含 讲解正文 / 考点提炼 / 原理与推导 / 易错点 / 真题印证 / 练习指向 六个标题行；至少一个单元有真题表格、至少一个有"无命中不等于不考"提示、至少一个有 `####` 摘录位；`coverage.md` 含三张表的标题与"无命中 **不等于** 不考"提示。产品目录按 bundle 写出的 `manifest.json` 位置定位，不写死路径。
- 全程只写系统临时目录，不写仓库路径。

## 3. 回退检查（`PYTHONDONTWRITEBYTECODE=1`）

改动前两文件 SHA-256：
- `tools/build_408_deck_scaffold.py` `a42453f18491b79b4dac2915c60ca76ec5665e117401a84157c0245ddd555996`
- `tools/extract_cs408_bundle.py` `0eda188808e076826b6e09c2be3275b11f3fd583dc61109a9ff8974c5789d40d`

| 变异 | 结果 |
|---|---|
| 在 `_unit_document` 中交换 `_unit_question_section` 与 `_unit_lecture_section` 两行 | **FAIL**：`deck/cs408.cn.chapter-01.section-01.md` 字节不同（`## 讲解正文` 出现在 `## 真题定位` 位置） |
| 删除 `*_unit_practice_section()`（模拟第 49 轮丢小节） | **FAIL** |
| `_write_manifest` 中删除 `"counts"` 键 | **FAIL**：`manifest.json` 字节不同 |

每次变异后用保存的原始字节恢复；恢复后两文件 SHA-256 与上表一致（逐字节还原）。

## 4. 验证

```
py -3.12 -m unittest tests.test_deck_scaffold_split_baseline tests.test_cs408_lecture_pipeline tests.test_tools_catalog
.....
----------------------------------------------------------------------
Ran 5 tests in 5.288s

OK
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 5. 建议

- 本轮基线测试把 `9cb8132` 当作"拆分前"版本；它与第 49/50 轮的迁移对照测试（`tests/test_cs408_lecture_pipeline.py`，基线 `762786f`）互补：后者管迁移允许的差异，本测试要求零差异。
- `_write_coverage`（56 行）若决策者希望按三张表拆成小函数，可另开一小包，现有基线测试可直接复用。
