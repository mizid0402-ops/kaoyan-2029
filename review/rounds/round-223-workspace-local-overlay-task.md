# 第 223 轮任务书：WP-T3 本地补充注册表 `kaoyan.workspace.local.yaml`（gpt-6-luna，续 luna-c）

## 背景

用户 2026-09-30："git 只提交不敏感信息"；"现有的 git 仓库只上传整个项目的骨架"，课表、学校档案与学习记录只在本机。
主注册表 `kaoyan.workspace.yaml` 进 git，所以个人文件改由一个 gitignore 的本地补充文件登记。
规格：`contracts/workspace.md` **§2.6**（新增）与 §6 的 `local_sha256`。`.gitignore` 已由决策者更新（`data/personal/`、`kaoyan.workspace.local.yaml`、学习状态目录、`staging/`）。

决策者已把个人文件移到 `data/personal/`（`timetable.yaml`、`schools/<学校>.yaml`、`availability.yaml`），并在本机写了一份本地补充文件。
**这些文件你只能读、不要改、不要把其中的学校名写进任何被跟踪的文件**（代码、测试、规格、报告里都不要出现用户学校的名字或其 ID）。

## 要做的

1. `ky/workspace.py`：按 §2.6 加载本地补充文件（位置、`schema_version`、允许的四个键、只增不改、路径语法、`local.` 前缀的字段路径、
   找到但无效即违约、`local_sha256`）。主注册表的加载逻辑不变；拆成有名字的小函数，行宽 ≤ 100。
2. 主注册表 `kaoyan.workspace.yaml`：删去 `state.availability` 这一行（它改由本地补充文件登记）。其他行不动。
   先 `rg -n "availability" tests` 找出读**仓库根注册表**并依赖它登记了 `state.availability` 的测试，改成用临时工作区或本地补充文件的写法，并在报告里逐个列出。
3. `tests/contract/test_timetable_port.py` 的真实数据用例：改为从仓库根注册表（含本地补充文件）取课表与学校，
   本机缺 `data/personal/` 文件或未登记时用 `tests/_resources.py` 的 `require_path` 方式 skip，提示"个人数据只在本机（`contracts/workspace.md` §2.6）"。
   断言里不要写学校 ID（从注册表取）。
4. `tests/contract/test_workspace.py` 补 §2.6 的契约用例：无文件时与只有主注册表**逐字段相同**且 `local_sha256 is None`；
   有文件时四个键各能生效；与主注册表重复的键 → `local.<键>`；未知键、`schema_version` 错、路径语法错、YAML 非法 → 违约；
   `--workspace` 指向别处时看那个目录；`local_sha256` 等于原始字节哈希。全部用临时工作区，不依赖本机的本地补充文件。

## 不做

- 不改 M18 / M26 / M8 / CLI 逻辑（T2 已完成的部分不动）；不改个人数据文件；不改 `.gitignore`。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_workspace tests.contract.test_timetable_port tests.contract.test_availability_port tests.test_cli
```

另外列出你在第 2 条里改过的测试模块，并只重跑它们。写完含中文的文件查 `rg -n '\?\?\?' <文件>`。

## 报告

`review/rounds/round-223-workspace-local-overlay-luna.md`：改动文件、做法、测试输出原文、"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、歧义与选择。
**报告里不要出现用户学校的名字或 ID。**
