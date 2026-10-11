# 第三轮：阶段 1 成果审查（真实代码审查，不是纸面评审）

## 背景

阶段 1 的代码**已经写完并跑通**。本轮是对**真实可执行产物**的审查，不是设计讨论。

### 已交付物

```text
F:\workspace\kaoyan-ai-system\
├─ ky\
│  ├─ __init__.py               包声明
│  ├─ __main__.py               preflight CLI（只读，零写入）
│  ├─ models.py                 合同模型 + 语义校验（JSON Schema 表达不了的跨字段约束）
│  ├─ contracts\__init__.py
│  └─ schedule\
│     ├─ __init__.py
│     ├─ budget.py              四科预算切分（先保底 min_daily_minutes，再按权重分余量）
│     └─ review_clip.py         复习容量裁剪核（确定性排序 + 软配额/硬上限 + backlog）
├─ tests\
│  ├─ __init__.py
│  ├─ test_contracts.py         合同与预算测试
│  ├─ test_review_scheduler.py  裁剪核测试
│  └─ fixtures\
│     ├─ config\{config-minimal,config-weights-not-closed,config-ratio-inverted}.yaml
│     └─ reviews\{reviews-normal,reviews-overloaded}.yaml
└─ pyproject.toml
```

### 实测运行结果（DSH 已跑，非声称）

```text
$ py -3.12 -m unittest -v tests.test_contracts tests.test_review_scheduler
Ran 49 tests in 0.318s
OK                                                        # exit 0

$ py -3.12 -m ky preflight --config tests/fixtures/config/config-minimal.yaml \
      --items tests/fixtures/reviews/reviews-overloaded.yaml --date 2026-09-12
project            : kaoyan-2029
daily budget       : 120 min
review soft / hard : 54 / 72 min (ratio 0.45 / 0.6)
due items          : 13
selected           : 6  -> 54 min
  - rv_math1_hard_0002       math1      12 min  overdue  10d  defers 0
  - rv_math1_urgent_0013     math1       8 min  overdue   0d  defers 2
  - rv_cs408_more_0010       cs408      10 min  overdue   0d  defers 0
  ...
deferred           : 7  -> backlog 64 min
  - rv_math1_more_0007       math1      10 min  overdue   0d  defers 1 (was 0)
  ...
new content budget : 66 min
  - 数学一 20 min / 英语一 25 min / 408 21 min
over capacity      : YES                                 # exit 0

$ # 合同违规路径
$ py -3.12 -m ky preflight --config tests/fixtures/config/config-weights-not-closed.yaml ...
contract violation: subjects: active subject weights must sum to 1.0 (got 0.9)   # exit 2
```

### 已实现的算法语义（请在审查时逐条验证是否与实现一致）

1. **失败即拒绝**：`ContractError` 携带精确字段路径（如 `subjects[2].weight`）；`preflight` 合同违规返回 exit 2，不"忽略非法值继续跑"。
2. **预算切分顺序**：先满足 `min_daily_minutes` 保底，再把余量按权重用最大余数法分配；余量分配结果一定精确加总到预算，不丢分钟。
3. **复习裁剪**：按 `(-逾期天数, -延期次数, -遗忘次数, -科目落后率, due_date, 类型优先级, 自评, review_id)` 的**全序**排序；在软配额内任何条目都可入选，超过软配额后**只有 urgent 条目**可以继续占用到硬上限。
4. **延期语义**：被延后的条目 `due_date` **原样保留**，只 `defer_count + 1`；不静默改期、不写回、不需要额外审计。
5. **超大条目**：单次成本超过硬上限的条目进 `unschedulable` 而不是在 backlog 里永久饥饿（导入时 > 30 分钟已被校验拒绝）。
6. **自评权限**：`self_rating` 只能做**全序的最后一级 tie-break**，不能改 due_date、不能改间隔、不能跳过复习。
7. **零写入**：整个包不读不写 `F:\workspace\study`，不创建生产项目，不调用 AI。

---

## 你的任务

### 如果你是 Codex（gpt-5.6-sol）——【独立审查者】

去**实际读代码**（`ky/models.py`、`ky/schedule/budget.py`、`ky/schedule/review_clip.py`、`ky/__main__.py`、两个测试文件、五个 fixture），
并**实际运行**它们（允许执行 `py -3.12 -m unittest ...` 与 `py -3.12 -m ky preflight ...`；`py` 启动器在本机不回显输出，**必须用 `py -3.12`**）。

交付 `F:\workspace\kaoyan-ai-system\review\rounds\round-3-codex.md`，包含：

- **A. 阻断级缺陷**：会导致错误计划、状态损坏、契约被绕过的具体问题。每条给
  `位置(文件:行)` / `触发条件` / `实际后果` / `最小复现` / `修法`。
- **B. 逻辑与边界**：排序键是否真的是全序？软/硬配额语义在"条目成本大于剩余额度但小于硬上限"时是否正确？
  保底与权重的先后顺序是否会产生用户意想不到的分配？浮点比较是否有隐患？日期比较是否有边界问题？
- **C. 与已定契约的偏差**：逐条对照上面"已实现的算法语义"1–7，指出**声称与实现不符**的地方。
  这一条最重要——如果实现做不到声称的语义，必须点出来。
- **D. 测试有效性**：49 个测试里哪些是**假测试**（断言过弱、只测实现细节、永远会过）？缺哪些关键反例？
  请给出你**自己写的新反例**（可以是代码片段或断言），至少 5 条。
- **E. 裁决**：阶段 1 是否达到"合同自洽、算法确定、不超预算"的验收门槛？给出 `通过 / 有条件通过（条件：…） / 不通过`。

### 如果你是 Claude Code（claude-sonnet-5）——【主实现者】

先**运行**现有测试与 preflight 复现现状，然后：

交付 `F:\workspace\kaoyan-ai-system\review\rounds\round-3-claude.md`，包含：

- **A. 自审**：你自己找出的实现缺陷（不要等 Codex 指出来），每条给位置、触发条件、后果、修法。
- **B. 对第 1–7 条语义的逐条自证**：哪条你用测试证明了，哪条只是"看起来对"但没有测试覆盖。
- **C. 修复**：对你在 A 里确认的缺陷**直接改代码**（`ky/` 与 `tests/` 下的文件），并补上对应测试。
  改完必须跑 `py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler` 并贴出真实结果。
  允许改：`ky/**`、`tests/**`。**不允许**改：`review/**`、`docs/**`，也不允许碰 `F:\workspace\study`。
- **D. 变更清单**：`文件` / `改了什么` / `为什么` / `验证方式`。
- **E. 仍未解决**：你没能修掉的，以及你觉得该由用户或审查者决定的问题。

---

## 共同约束

- 用**中文**。
- 允许执行 `py -3.12 ...` 命令与读取任何本目录文件；**禁止**修改 `F:\workspace\study` 下任何文件，禁止 `git` 操作。
- 不要写操作确认语，正文直接进你的输出文件。
- 结论必须基于**实际运行结果**，不得凭阅读猜测；跑不动就说跑不动。
