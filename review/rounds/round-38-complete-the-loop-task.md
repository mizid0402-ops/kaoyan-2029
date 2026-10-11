# 任务：补齐②的两处残项（round-37 的已知未打通）

> 实施者：Claude Sonnet 5（high）。**主控审查。**
> 前置：`879f00b`（round-37 实施）与其后的 `e42c0d5` 已提交，工作区干净。

---

## 0. 开工前

1. `git status` 确认干净；记测试基线（当前 **398 tests / OK**）。
2. 记 `ky/schedule/monthly_close.py`、`ky/__main__.py`、`ky/storage/day_plan_store.py`、
   `ky/schedule/completion.py` 的 SHA-256（报告里给前后对比）。

**背景**：round-37 自己如实报告了两处"只搭了一半"。主控已独立复核，**两条都成立**：

```
monthly_close.py 里搜不到 CompletionEvent      → 它仍只吃 DayPlan（"计划"），
                                                 任务书 §6 说这"是错的"，但没改
ky/__main__.py   只调 write_completion_event()  → 没有把 advance_review_item 的结果
                                                 写回复习队列
```

---

## 1. 残项 A：完成事件必须真正推进复习队列（**这是要害**）

### 问题

用户已定：**复习项推进状态机归入"AI 分配学习"板块**。round-37 建了
`ky/schedule/completion.py::advance_review_item(item, completion) -> ReviewItem`，
**函数是对的（17 个测试）**，但：

- `day-plan record` **只把完成事件写进 `DayPlanStore`**
- **没有把它写回复习队列**（`ky/storage/review_shards.py` 的 `ReviewShardStore`）

**后果：复习队列仍然是死的。** 完成的复习不会往后排，`review_clip.py` 的排序核
**会一直基于"从未完成过"的假设运行**——这正是用户要求归入本板块要解决的问题。

### 要求

把链条打通：**完成事件 → 推进 `ReviewItem` → 写回复习队列**。

- 读 `ky/storage/review_shards.py` 了解 `ReviewShardStore` 的写路径与契约
  （它硬编码 `ReviewItem` 字段，`validate_review_item` 会校验）
- 对每个 `ReviewCompletion`：
  1. 从队列取出对应 `ReviewItem`
  2. 调 `advance_review_item()` 得到推进后的项
  3. **写回队列**（用 `ReviewShardStore` 既有的写路径，不要另造一套）
  4. **推进后的项必须仍通过 `validate_review_item()`**
- **没有对应 `ReviewItem` 的完成事件**（例如复习项已被删、或 id 打错）：
  **必须报告为错误，不得静默丢弃**
- `day-plan record` 要能指定复习队列存储位置（现有签名缺这个参数位）
- **幂等**：同一个完成事件重复提交，**不得重复推进**（否则 `interval_days` 会重复翻倍）

### 完成标准

1. **端到端测试**：建一个含若干 `ReviewItem` 的队列 → 提交 `CompletionEvent` →
   **读回队列，断言 `due_date` / `interval_days` 确实变了**（不是只断言函数返回）
2. **幂等测试**：同一事件提交两次，队列状态与提交一次相同
3. **未知 review_id** → 报错且**队列不变**
4. **推进后的项仍通过既有契约校验**（quality 0..5 全覆盖）
5. **变异测试**：把"写回队列"那一步去掉 → 端到端测试必须变红 → 还原 → **给前后哈希**

---

## 2. 残项 B：`monthly_close` 要能区分"计划"与"实际"

### 问题

`monthly_close.close_month(plans)` **只吃 `DayPlan`**，把"计划"当作"实际发生"来汇总。
任务书 §6 原文就写了"这是错的"，但 round-37 只新建了 `CompletionEvent` 模型，
**没有反过来改 `close_month`**。

**后果**：月度闭环的账本**记的是计划，不是实绩**。而"月度闭环"的意义恰恰是
**看到实际发生了什么**。

### 要求

- 让月度结算**能消费 `CompletionEvent`**，并**同时呈现计划与实际**
- **不要**把两者合并成一个数——**分别报告**：
  - 计划了多少（来自 `DayPlan`）
  - 实际完成了多少（来自 `CompletionEvent`）
  - **差额**（未完成 / 超额）
- **`close_month` 的既有调用方不许破坏**：既有签名与行为**保持不变**
  （新增可选参数或新增函数，二选一，并说明理由）
- **投递 ≠ 掌握**：`delivered_words` 与 `practiced_words` **分开统计**，不得相加
- **不产出任何"下月该给多少"类字段**（沿用 `test_close_does_not_prescribe_next_month` 的约束）

### 完成标准

1. 只有计划、没有完成事件时 → 行为与今天一致（既有测试不改而通过）
2. 有计划 + 有完成事件时 → **两者分别出现，且差额可核对**
3. `delivered_words` 与 `practiced_words` 分别计数，**有测试证明它们没被相加**
4. 无完成事件的月份 → 如实报告"无实绩记录"，**不得当成"完成了 0"或"完成了全部"**
5. 禁用函数名扫描（`recommend*/suggest*/default*/optimal*/next_month_*`）**仍然 0 命中**

---

## 3. 完成标准（总结）

| # | 标准 |
|---|---|
| 1 | 完成事件端到端推进复习队列，**读回队列可见 `due_date` 已变** |
| 2 | 重复提交幂等 |
| 3 | 未知 review_id 报错且队列不变 |
| 4 | 推进后仍通过契约校验（quality 0..5） |
| 5 | 两处残项各有**变异测试 + 还原哈希** |
| 6 | `close_month` 既有调用方不破坏；计划与实际分别呈现 |
| 7 | `py -3.12 -m unittest discover -s tests -q` **全绿**，测试数 **> 398** |
| 8 | 禁用函数名 **0 命中** |
| 9 | `data/english_vocabulary/eng1_vocabulary.sqlite` 哈希仍为 `839d48be…`（**不得触碰**） |

---

## 4. 附带说明（不必修，但要如实报告）

`tools/daily_words.py` **仍会写词库的 `delivery_log`**——round-37 未改它，理由是
`tools/**` 不在其允许范围内。本次**仍不授权改 `tools/**`**，但要在报告里确认：
**这条旧路径是否依然会让词库哈希变化**；若是，说明"冻结"目前是
"新系统绕开它"而非"旧脚本被物理禁止"。

---

## 5. 纪律

- **可改/可新建**：`ky/**`、`tests/**`、`review/rounds/**`
- **禁止改**：`data/**`（含词库、树、索引）、`docs/**`、`tools/**`、`review/408知识点树与真题/**`
- **不许改 `review_clip.py` 的排序算法**（只许它已有的可选参数）
- **不许为了让测试通过而放宽验证**——本轮是**接通**，不是放宽
- 本机**没有 `rg`**，用 Glob/Grep 或 `Get-ChildItem -Recurse`
- 必须用 `py -3.12`；终端吞中文，结果写 UTF-8 文件再读
- **改完 `git add -A && git commit`**（不要 push）
- 报告写 `review/rounds/round-38-complete-the-loop-claude.md`

## 6. 报告必须含

1. 开工前 `git status` + 测试基线 + 四个文件的开工前 SHA-256
2. 残项 A 怎么打通的（具体调用链）
3. 残项 B 怎么改的（新增参数还是新增函数，理由）
4. 9 条标准的**实际输出**（原始命令 + 结果）
5. 两处变异测试的**结果 + 还原哈希**
6. `tools/daily_words.py` 旧路径是否仍会改词库哈希（实测）
7. 「我实测到了」vs「我推断」
8. 没有把握的地方至少 3 条

最后用一句话回复：残项 A/B 是否打通 + 9 条标准过了几条 + 测试数 + 提交哈希 + 报告路径。
