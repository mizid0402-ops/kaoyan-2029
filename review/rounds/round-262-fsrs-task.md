# 第 262 轮任务书：FSRS 接管复习时间（M10 第二个算法实现）（gpt-6-luna，luna-a 新会话）

## 先读

`AGENTS.md`（全文）；规格 `contracts/review_progress.md` 末节"FSRS 算法"（本包唯一依据）、`contracts/config.md` §2.3、`contracts/learning_state_projection.md`、`contracts/projection.md`（schema 版本规则）；
sol 第 261 轮初检 `review/rounds/round-261-fsrs-spec-review-sol61.md`（若有"必须改"，决策者已改进规格，以规格为准）。
现有实现：`ky/schedule/completion.py`（`ReviewAlgorithm` 协议、`LadderSm2Algorithm`、`reset_for_relearning`）、`ky/models.py`（`ReviewSchedule`、schedule 校验、`ReviewPolicy`、`VALID_SCHEDULE_MODES`）、
复习项写盘（`ky/storage/review_shards.py` 与 `ky/models.py` 的映射函数）、调用 `advance_review_item` / 算法的地方（`grep -rn "advance_review_item\|LadderSm2Algorithm\|self_rating_mode" ky`）、`ky/projection/`。
`py-fsrs` 6.3.2 已装在本机（`import fsrs`），**不要再 pip install**。

## 工作区

主仓库 `F:\workspace\kaoyan-ai-system`，master 当前提交之上。另一个窗口稍后会做 M30 / M17，不碰 `ky/charts/`、`ky/mastery/`。

## 要做的

1. `FsrsAlgorithm` 实现 `ReviewAlgorithm` 协议（新文件 `ky/schedule/fsrs_algorithm.py`，模块头写 M10、规格、对外接口）；规格里的 `Scheduler` 参数、时刻、评分映射、模式切换、未核对完成、D11 全部照做。
2. `ReviewSchedule` 增加可选 `stability` / `difficulty` / `fsrs_reviewed_on`（FSRS 记忆时钟，与 `last_reviewed_on` 分开，sol 261 F1）；`VALID_SCHEDULE_MODES` 加 `fsrs`；schedule 校验与读写映射：`fsrs` 模式三字段必填且合法（有限数、范围、ISO 日期），其他模式出现即拒绝；
   **非 fsrs 复习项的写盘字节不变**（字段缺省时不写出）。
3. 配置 `review_policy.algorithm`（`ky/models.py` 的配置校验与 `ReviewPolicy`）；按配置选择算法的地方只有一处（工厂函数），所有调用方经它取算法，不在调用方各写 if。
4. 投影：`review_items` 加 `stability REAL NULL`、`difficulty REAL NULL`、`fsrs_reviewed_on TEXT NULL`；`PROJECTION_SCHEMA_VERSION` 4 → 5，`contracts/projection.md` 标题与 §"版本"同步；投影契约测试按新版本更新。
5. `pyproject.toml` 依赖加 `"fsrs>=6,<7"`；`docs/模块地图.md` M10 行写明"两个算法实现：阶梯（缺省）/ FSRS（`review_policy.algorithm: fsrs`）"；`docs/技术债与整改清单.md` 不动。

## 不做的

不改 M9 裁剪与排序；不改复习项创建规则；不调用 FSRS 优化器；不改既有命令在 `algorithm` 省略时的任何输出；不读 `data/personal/`；不改用户的个人配置（决策者做）。

## 测试（只写这些）

- 新 `tests/contract/test_fsrs_algorithm_port.py`：
  - 三种结果 → Good / Hard / Again 后的 `stability` / `difficulty` / `interval_days` / `due_date` 与直接调用 `fsrs.Scheduler`（同参数）的结果一致；`repetitions` / `lapses` 计数；
  - 阶梯模式项第一次已核对完成 → 变 `fsrs` 模式（按新卡）；未核对完成（strict 四档自评、lenient 四档）记忆状态不变，间隔规则同 D9 表，且**不长于**无自评结果；
  - `reset_for_relearning` 对 fsrs 项保留 `stability` / `difficulty` / `fsrs_reviewed_on` / `lapses`；
  - sol 261 F1：10-01 已核对 → 10-30 未核对（fluent）→ 10-31 已核对，FSRS 按 30 天经过计算（与直接调库、last_review=10-01 一致），`last_reviewed_on` 仍记 10-30；
  - sol 261 F2：先推进 10-10 的核对，再到 10-05 的已核对补录（不同 completion_id）→ FSRS 不调用、七个字段不变、推进报告 `fsrs_late_checks` 有该条、CLI 打印提示；同日第二次核对照常调用；
  - 切回 `ladder`：fsrs 项下一次已核对 → `sm2_lite`、去掉三字段；
  - 同一输入两次运行结果完全相同（无扰动）；`interval_days` 不超过 180。
- `tests/test_contracts.py` 或配置契约测试：`algorithm` 合法 / 非法值与路径；省略时等价 `ladder`。
- 复习项读写：fsrs 项往返不丢精度；fsrs 模式缺字段 / 非 fsrs 模式带字段 → 契约错误带路径；**一份既有阶梯模式队列文件读入再写出逐字节相同**。
- `day-plan record --review-store` 在 `algorithm: fsrs` 配置下推进一条复习项的端到端用例（临时工作区）。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_fsrs_algorithm_port tests.test_completion tests.test_contracts tests.contract.test_config_port tests.test_review_queue_advance tests.contract.test_learning_state_projection tests.contract.test_projection_port tests.test_cli
```

报告 `review/rounds/round-262-fsrs-luna.md`：改动、做法、测试输出原文、"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"、歧义与选择、怀疑受影响但未点名的模块。
不提交；中文字符串写字面量，不要写成 `\uXXXX`；含中文的文件只用 `apply_patch`；写完 `rg -n '\?\?\?'` 检查。
