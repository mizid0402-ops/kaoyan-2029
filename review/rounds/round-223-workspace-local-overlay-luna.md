# 第 223 轮：本地补充注册表

## 改动

- `ky/workspace.py`：主注册表仍先用原解析流程校验；之后从同目录尝试读取 `kaoyan.workspace.local.yaml`。只把文件不存在视为无本地登记；找到但读不了、YAML 不合法或字段不合规均抛 `ContractError`，字段路径以 `local.` 开头。按 §2.6 接受四个指定键，路径相对 `Workspace.root`，与主表重复时拒绝，不合并映射。解析和 SHA-256 使用同一份本地原始字节；`Workspace.sha256` 仍只哈希主表，`local_sha256` 在无本地文件时为 `None`。
- `kaoyan.workspace.yaml`：只删除 `state.availability` 一行，其余主注册表内容未改。
- `tests/contract/test_workspace.py`：加入纯临时工作区的覆盖，包括无本地文件逐字段相同、四键生效、重复键、未知键、版本、路径、非法 YAML、显式工作区目录和原始字节哈希。
- `tests/contract/test_timetable_port.py`：真实数据用例从根 `Workspace` 读取登记，不再写死档案路径或登记键；缺个人登记/数据时通过 `require_path` 或同一恢复提示跳过：“个人数据只在本机（`contracts/workspace.md` §2.6）”。
- 第 2 条中调整了以下根注册表复制逻辑：`tests/contract/test_exam_index_port.py`、`tests/contract/test_knowledge_tree_port.py`、`tests/contract/test_projection_port.py`、`tests/contract/test_subject_onboarding.py`。它们不再尝试从主表复制已移出的 availability 文件；各自的合成工作区仍按测试需要构造。

本地补充文件及 `data/personal/` 下的内容只通过路径存在性检查和授权的真实数据用例读取，没有改动；个人档案标识未写入本报告、代码或测试。`.gitignore` 未改。

## 验证

验收命令首次运行：

```text
py -3.12 -m unittest tests.contract.test_workspace tests.contract.test_timetable_port tests.contract.test_availability_port tests.test_cli
.......s.........E..................................................................................
======================================================================
ERROR: test_local_overlay_registers_each_allowed_key (tests.contract.test_workspace.WorkspaceContractTests.test_local_overlay_registers_each_allowed_key)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "F:\workspace\kaoyan-ai-system\tests\contract\test_workspace.py", line 1052, in test_local_overlay_registers_each_allowed_key
    workspace.require("settings.exam_config"),
  File "F:\workspace\kaoyan-ai-system\ky\workspace.py", line 195, in require
    return self._check_required_path(key, path, is_dir=is_dir)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "F:\workspace\kaoyan-ai-system\ky\workspace.py", line 170, in _check_required_path
    raise ContractError(f"registered {expected} does not exist: {path}", key)
ky.models.ContractError: settings.exam_config: registered file does not exist: C:\Users\Lenovo\AppData\Local\Temp\tmpoj1zb4ff\personal\config.yaml

----------------------------------------------------------------------
Ran 116 tests in 41.492s

FAILED (errors=1, skipped=1)
```

失败原因是测试夹具未创建已登记的 config 文件；实现按 `require()` 契约拒绝了缺失文件。补齐临时夹具后，只重跑受影响的工作区模块：

```text
py -3.12 -m unittest tests.contract.test_workspace
.......s.......................
----------------------------------------------------------------------
Ran 31 tests in 0.813s

OK (skipped=1)
```

第 2 条调整的四个测试模块：

```text
py -3.12 -m unittest tests.contract.test_exam_index_port tests.contract.test_knowledge_tree_port tests.contract.test_projection_port tests.contract.test_subject_onboarding
..........................................
----------------------------------------------------------------------
Ran 42 tests in 23.495s

OK
```

`git diff --check` 通过；本轮编辑的中文文件 `rg -n '\?\?\?'` 无命中。验收整组的首次运行跑完 116 项，其中仅上述夹具错误，其余通过；按 `AGENTS.md` 只重跑修正影响的 `test_workspace`，未重跑整组。全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 歧义与选择

- 本地文件缺失按“无本地登记”处理；除 `FileNotFoundError` 外的读取错误视为已找到但无效，路径为 `local`。
- `reference.timetable_schools` 是一个整体键；主表已有该键时拒绝本地映射，不做逐项合并。
- 本地 YAML 语法或构造错误归到 `local`；结构、版本及字段值错误使用尽可能具体的 `local.<字段路径>`。
