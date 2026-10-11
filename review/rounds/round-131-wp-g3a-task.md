# 任务书：WP-G3a 拆分 `load_workspace`（D7，M0）

先读仓库根 `AGENTS.md`（尤其"最高原则"里"一个函数做一件事、超过约 60 行拆成有名字的辅助函数"，以及 11–13、12a"重构输出不变"），再读：
`contracts/workspace.md`、`ky/workspace.py`（`load_workspace` 约 216 行）、`tests/contract/test_workspace.py`。

你是固定窗口 `luna-a`（负责 CLI、存储与状态端口：M0 / M13 / M14 / M27），之后同一区域的任务还会派到这个窗口。
在主仓库 `F:\workspace\kaoyan-ai-system` 工作，**只改 `ky/workspace.py`，新增一个对照测试文件**。另一个实现者正在同一仓库做 `tools/` 分层（WP-G2b），不要碰 `tools/`、`docs/`、`README.md`。

## 要做的

把 `load_workspace` 拆成若干有名字的私有辅助函数（例如按注册表的顶层段：科目档案、reference、supplementary、materials / products / settings / state / staging / projection 等），
`load_workspace` 自身只剩"选文件 → 读字节 → 解析 → 依次调用各段 → 组装 `Workspace`"。每个辅助函数一件事、不超过约 60 行、嵌套不超过三层。

**行为逐字节不变**：
- 同一注册表得到相等的 `Workspace`（所有字段）；
- 每一种非法输入抛出的 `ContractError` 的**消息与路径完全相同**，且多处同时出错时**先报的那一处不变**（校验顺序不变）；
- 不改公开接口、不改 `contracts/workspace.md`、不加兼容别名、不改其他函数。

## 测试（只写这一个）

`tests/contract/test_workspace_split_baseline.py`（`AGENTS.md` 12 / 12a）：用 `git show fa9e11c:ky/workspace.py` 取旧版（断言取到的确实是旧版，例如旧版 `load_workspace` 超过 150 行），
作为独立模块加载；以仓库的 `kaoyan.workspace.yaml` 为种子，在系统临时目录生成一组变体——合法原样、每个顶层键缺失、类型错误、未知键、非法科目 ID、路径越界 / 反斜杠 / 绝对路径、
`syllabus_versions` / `paper_shapes` / `weight_batches` 的各类错误、以及**两处同时出错**的若干组合——对每个变体分别调用新旧 `load_workspace`：
合法的比较 `Workspace` 相等，非法的比较异常类型、`str(exc)` 与路径。变体从种子**按规则生成**，不写死科目名或数量（D5 / D6）。

撤修改验证：临时把某个辅助函数里两项检查的顺序对调，这个测试应变红；报告写实际命令与结果。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_workspace tests.contract.test_workspace_split_baseline
```

## 报告

`review/rounds/round-131-wp-g3a-luna.md`：拆出的函数清单（名字、行数、负责哪一段）、对照测试覆盖的变体类别与数目、撤修改验证、验收输出、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
