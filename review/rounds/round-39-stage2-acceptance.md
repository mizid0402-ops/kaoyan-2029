# 阶段②验收：模拟真实数据试跑结果与残项清单

> 日期：2026-09-16 ｜ 主控执行 ｜ 提交前置：`0cd4843`（round-38 补齐）

---

## 一、为什么要"模拟真实数据"

阶段②的所有验证此前都建立在**测试夹具**上。按项目既有纪律
（"测试全绿不等于可用"），阶段②的出口门槛应当是**用真实形态的数据跑出结果**。

**但实测发现：仓库里没有任何真实学习状态。**

```
data/review_queue/          0 个文件
data/monthly_reports/       0 个文件
data/study_records/         0 个文件
data/ability_profile/       0 个文件
data/course_schedule/       0 个文件
```

所以"真实数据"只能**从真实知识树合成**：把三棵树的 `item` / `section` 节点
转成 `ReviewItem`，日期围绕一个模拟"今天"铺开（含逾期、今日到期、未来三段）。
**模拟脚本与完整输出保存在** `review/rounds/artifacts/stage2-realsim.md`。

---

## 二、模拟场景

| 项 | 值 |
|---|---|
| 模拟"今天" | `2027-03-01` |
| 目标考试日 | `2029-12-21` |
| 生成复习项 | **427** |
| 按科目 | cs408 **359** / math1 **44** / eng1 **24** |
| 按粒度 | `concept` 254 / `question_pattern` 173 |
| 到期分布 | **逾期 150** / 今日 4 / 未来 273 |
| 队列估算总时长 | **3392 分钟** |

配置用仓库既有的 `tests/fixtures/config/config-minimal.yaml`（其中已固化 40/20/40 决议）。

---

## 三、试跑结果

```
$ py -3.12 -m ky snapshot --config <cfg> --items <items> \
      --date 2027-03-01 --target-exam-date 2029-12-21
exit=0

as of 2027-03-01
days to exam       : 1026
math1      tree:  69 items (tree_status=extracted)
           queue   44  due-today   0 (  0 min)  backlog 144 min
eng1       tree:  24 items (tree_status=extracted)
           queue   24  due-today   0 (  0 min)  backlog  66 min
cs408      tree: 403 items (tree_status=extracted)
           queue  359  due-today   4 ( 38 min)  backlog 956 min
politics   tree: no committed tree
           queue    0  due-today   0 (  0 min)  backlog   0 min
vocab delivered    : 15
vocab remaining    : 3137
```

`--json` 同样 `exit=0`，字段可机读；**`git status` 改动 0 条**（快照确实只读）。

### 三条从这次试跑读出来的结论

**1. 契约是活的——它三次拒绝了我造的脏数据**

| 我填错 | 契约反应 |
|---|---|
| 把 scope 词表当 `granularity`（填了 `section`）| 拒绝：只接受 `concept/procedure/question_pattern/error_pattern/vocabulary_batch` |
| 用了别的系统的 `self_rating`（`again/hard/easy`）| 拒绝：只接受 `unknown/vague/basic/fluent` |
| `last_reviewed_on` 早于 `introduced_on` | 拒绝并指出具体日期 |

**三次都是我的数据错、系统的判断对。** 这比"一次跑通"更能说明契约有效。

**2. `tree_status=extracted` 如实出现在每一个来自知识树的数字上**

三棵树均未核准（无一个 `approved`），而契约规定 `extracted` **不得用于覆盖率类统计**。
快照**没有把未审核的计数伪装成权威覆盖率**——这条要求落实了。

**3. 复习容量远超日预算（真实形态，非缺陷）**

队列 427 项、3392 分钟；**仅 cs408 一家 backlog 就 956 分钟**，而日预算 120 分钟。
这**印证了 `docs/评审结论与实施契约.md` §4.1 的预警**："稳态复习需求中位约 250 分钟/天，
是 120 分钟预算的 2 倍以上"。

**系统对此的处置是正确的**：如实报 `backlog`，**不偷借未来时间、不静默改 `due_date`**。

---

## 四、残项清单

| # | 残项 | 实测 | 影响 | 状态 |
|---|---|---|---|---|
| **R1** | **词库写入路径共 4 个** | `daily_words.py` / `build_eng1_vocabulary.py` / `verify_eng1_vocabulary.py` / `vocab_channel.py` 均可写 `delivery_log` | **对已有产出零影响**（哈希仍 `839d48be…`）；但**"永久只读"是约定不是强制** | ⏸ **等授权改 `tools/**`** |
| **R2** | `vocab`/`phrase` 的单单元上限仍是**通道总量**（知识通道已下放到按科目）| `ky/schedule/longitudinal.py` | **语义上可接受**——词汇是批量抽认，本无"单项"粒度 | ✅ **建议判定为可接受**，仅需文档写明 |
| **R3** | **`stage1_input_hash` 没有生产者** | `planning.py` 有该字段 + 形状校验；**全仓库无人计算它，也没定义对哪些文件算** | **看起来像验证、实际不验证**——与"验证器能被关掉"同类 | ⚠️ **建议修**：要么真算、要么去掉 |
| **R4** | `data/` 下 5 个学习状态目录**全空** | 见 §一 | 阶段②尚未被真实使用；非缺陷 | ℹ️ 事实记录 |
| **R5** | 知识树全部 `extracted`，无 `approved` | 三棵树均无核准节点 | 依赖权威基线的指标（覆盖率/能力画像）**不可用** | ⏸ 需人工核准，非本阶段范围 |

### R1 补充：不止一个写入口

残项报告原文只提到 `daily_words.py`。实测**有四个文件能写 `delivery_log`**：

```
tools/daily_words.py                opens read-write, INSERT/DELETE delivery_log
tools/build_eng1_vocabulary.py      writes delivery_log
tools/verify_eng1_vocabulary.py     writes delivery_log
ky/schedule/vocab_channel.py        references delivery_log
```

**所以"冻结"目前的准确表述是**：新投递路径（`CompletionEvent` → `day_plan_store`）
**绕开了 sqlite**；而**旧路径仍然可写**。哈希至今未变，是因为**没人跑那些旧脚本**。

---

## 五、阶段②的最终状态

| 项 | 状态 |
|---|---|
| 测试 | **306 → 419 全绿** |
| 五步 | 护栏修复 / `review_clip` 逐日预算覆盖 / `RoutePlan`+状态快照 / 落盘+CLI / 完成推进状态机 **全部完成** |
| 提交 | `879f00b`（主体）→ `0cd4843`（补齐）→ `ff4ce35`（报告勘误） |
| 关键链条 | **完成事件 → 推进 `ReviewItem` → 写回复习队列** —— 端到端验证通过（9 个测试，含"读回队列断言 `due_date` 已变"与幂等） |
| 真实数据试跑 | **通过**（本文件 §三） |

**②可以收尾。** 待办只有 R1（需授权）与 R3（需先定义"阶段①输入"）。
