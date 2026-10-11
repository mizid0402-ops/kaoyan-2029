# 任务书：修复 sol 第 94 轮对 WP-E2（`8f31a05`）的意见

先读 `review/rounds/round-94-review-sol-out.md`（每条有复现输入）。遵守 `AGENTS.md`。E2 已提交，你在主工作区改，不提交。

## 必须改

1. **H1 信任边界（决策者裁定）**：本机单用户系统没有身份认证，"AI 产物零特权"靠的是**谁能执行 apply**。
   - `contracts/planner_port.md` 新增"信任边界"一节，写明：AI 进程只允许写 `staging/`；`ky day-plan submit`（两种形式）由用户本人或其信任的编排者执行，AI 进程不得调用；
     提案里的 `actor` 是**声明**，用于审计，不是认证；`--plan` 是用户直接提交通道，记为 `human`。
   - 收紧：`staging/day_plans/` 里的提案**一律必须带 `input_hash`**（`actor: human` 也不例外），使走 staging 的写入都有过期保护；`input_hash: null` 只可能来自 `--plan`。补负例。
   - README"五、设计原则 / 三条硬不变量"第 2 条后加一句指向该节（一句话，不改其余文字）。
2. **H2 输入包写入**：`create_planner_input` 改为同目录临时文件写入、再 `os.replace` 到目标（不打开、不改写已存在的目标 inode）。
   仓库里已有两份同样的写法（`ky/storage/day_plan_store.py` 的 `_write_atomically`、`tools/aggregate_topic_weights.py` 的 `_replace_file`）：
   把原子替换写入提升为 M13 的一个**公开**函数（例如 `ky/storage/atomic.py` 的 `replace_bytes(path, data)`，模块头写明用途与"替换而不写穿"的理由），M19 与聚合工具改用它；`day_plan_store` 内部若语义相同也改用（它有重读校验回调，签名不同就保留原函数，报告里说明）。
   补回归：输入包目标是指向工作区外文件的硬链接时，外部文件不变（仿照 `tests/contract/test_topic_weights_port.py` 的硬链接测试，无权限时 skip）。
3. **I1 预检载荷单一来源**：`ky preflight --json` 的载荷（含 `subject_allocation`、`config`）目前在 `ky/__main__.py` 里拼装。把它提到公开函数（放在复习裁剪 / 预算所属模块，例如 `ky/schedule/review_clip.py` 或新建 `ky/schedule/preflight.py`，按 D7 选最合适的一处），CLI 与 M19 共用；
   输入包的 `review_clip` 字段改为这份完整载荷（`config` 若与输入包顶层 `config` 重复，在规格里说明取舍，二选一，不要两份不同形状的配置）。
   **`ky preflight --json` 输出逐字节不变**（固定基线 `8f31a05`，同一临时工作区对比）。规格同步。

## 同时做

4. **I2**：规格把"过期"写明为"规划者可见的输入包内容发生变化"，并列出不会触发过期的变化类别（例如复习项标题不在包内）。
5. **E1**：规格写明过期检查发生在写入前、与写入不在同一事务，不保证并发修改下的写入瞬间新鲜度。
6. **S1**：提案 `schema_version` 用精确整数校验（`true` 不算 1）；补负例。
7. **M1**：规格强调 `day_plan_provenance(day)` 只给**当前版本**的来源，历史版本的来源不保留。

## 不做的

不做 E3 / E4；不改 manifest 格式；不改过期检查的比较方式。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_planner_port tests.test_cli tests.test_day_plan_store tests.contract.test_topic_weights_port tests.test_review_scheduler tests.test_contracts
py -3.12 tools/aggregate_topic_weights.py --check
```

每条新负例临时撤掉对应修复确认变红，再还原，写进报告。

## 报告

`review/rounds/round-95-wp-e2-sol94-fixes-luna.md`：逐条落点、`preflight --json` 逐字节对照结果、撤修复记录、验收输出。全量：未跑。不提交。含中文文件查 `???`。
