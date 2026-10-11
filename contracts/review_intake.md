# M32 学完入队（`ky learn`）

> 决议来源：用户 2026-10-01 选"先补缺口再试运行"。状态：sol 269 初检 FAIL（M1 空队列读取）→ 已改。
> 缺口：复习队列此前只能读 / 推进 / 检查 / 迁移，没有"学完一个知识点 → 进复习队列"的入口；日计划只记新学分钟，不记学了哪个知识点。

## 1. 命令

```
py -3.12 -m ky learn --date D (--knowledge-point ID ... | --leaves-under ID) [--minutes N] [--dry-run] [--workspace W]
```

- `--knowledge-point` 可重复：把这些知识点各建一条复习项。
- `--leaves-under ID`：把 `ID` 之下的**全部可学叶子**各建一条（例如学完一章的"考试要求"，一次全加）；`ID` 本身不建。
- 两者恰好给一个；`--date` 必填（学完的那天，不读当前时间）；`--minutes` 是每条预计复习分钟，缺省见 §3。
- 退出码：成功 0；契约违约 2；用法错误 3。`--dry-run` 只打印将建的复习项，不写。

## 2. 校验（任一不过 → 违约退出 2，**一条都不写**）

1. 知识点在该科**生效知识树**（注册表 `reference.knowledge_trees.<科目>`，科目取 ID 第一段）里，且是**可学节点**（M4 `learnable_tree`：不是跟踪节点）。
2. 该科在考（配置 `active: true`）。
3. 该知识点没有状态为 `queued` / `scheduled` 的复习项（不重复入队）；已有则报"已在复习队列"并给出该项 `review_id`。
4. `--leaves-under` 的结果里，已在队列中的叶子**跳过**并列出（不算错误）；结果为空 → 违约"没有可加入的叶子"。
5. 同一次命令里重复给同一个知识点 → 用法错误 3。

## 3. 新复习项的字段

| 字段 | 值 |
|---|---|
| `review_id` | `rv-<knowledge_point_id>`；若该 ID 已被**全队列任一项或本批已分配的项**占用，依次用 `rv-<ID>-2`、`-3`… |
| `revision` | 1 |
| `subject_id` | ID 第一段 |
| `knowledge_point_id`、`title` | 知识点 ID 与知识树 `title` |
| `granularity` | `concept` |
| `state` | `queued` |
| `estimated_minutes` | `--minutes`，缺省 `DEFAULT_REVIEW_MINUTES = 5`（本模块常量，与第一周模拟同口径；以后由复盘数据再定） |
| `introduced_on` | `--date` |
| `due_date` | `--date + 1` 天（与现有新项规则一致：次日第一次复习） |
| `last_reviewed_on`、`last_quality`、`last_self_rating` | 空 |
| `schedule` | `fixed_bootstrap`、phase 0、`interval_days 1`、`ease_factor 2.5`、`repetitions 0`、`lapses 0`（首次已核对完成时按配置的算法接管，FSRS 见 `contracts/review_progress.md`） |
| `defer_count` | 0 |

## 4. 写入

- 读当前队列一次，用 `ReviewShardStore.read_state_sources().items`（sol 269 M1：它把"目录或 manifest 不存在"读成空队列，而 `load()` 会报错；manifest 损坏、目录位置是文件等仍报错，不当空队列），追加新项，用 `ReviewShardStore.write()` 一次原子写入（沿用其 manifest 与哈希规则）。
  `state.review_queue` 必须已登记（未登记 → 违约，提示登记）。
- 不写完成事件、不改日计划；输出每条新项的 `review_id`、知识点标题、首次复习日。

## 5. 模块

新模块 `ky/review_intake/`（纯函数 `new_review_items(...)` 产出复习项 + CLI 装配）；`docs/模块地图.md` 登记 **M32**。
