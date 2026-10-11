# 第 261 轮：FSRS 接管复习时间与 M30 修订规格初检 — FAIL

范围：任务书点名的五份规格、现有 schedule/推进/裁剪接口及本机 FSRS API；只读初检。
未联网、未读个人学习状态；仅写本报告，不改实现、不跑测试。

## 已确认

- 本机 `py-fsrs 6.3.2`：Card 支持 state/stability/difficulty/due/last_review；review_card 返回 (Card, ReviewLog)。
- Scheduler 支持规格全部参数；空 learning/relearning_steps、关闭 fuzzing 后返回整数日间隔，库自身限制在 1..180。
- Good/Hard/Again 枚举存在；评分来自核对结果，不来自自评；未核对分支不调用 FSRS 的方向正确。
- fsrs 模式、两项记忆字段及 phase=5 需扩展现有模型校验，这是本包明示的新接口；不能遗漏序列化与旧模式字段拒绝。
- M9 仍只裁剪 due_date/耗时并读 lapses，不需要依赖 FSRS；D8′ completion_id 去重与记忆状态仍应同次提交。
- 259 M1–M3：均已解决。显式 weighted_mastery 开关；日期同源且处理无效区间/null 能力；叶子输出所选组最大 lapses。
- M30 fsrs 用稳定度、其他模式用间隔的分支明确；两者均可应用 7/30 门槛，未核对时不应提升稳定度档位。

## 必须改

### F1：FSRS 记忆时钟不能复用“最近一次完成”日期
- 位置：review_progress“FSRS 状态/未核对完成”；现有 completion.py:183、day_plan_store.py:480 会更新 last_reviewed_on。
- 反例：10-01 已核对；10-30 check=none/self_rating=fluent；10-31 再核对。按现稿还原 last_review=10-30，
  FSRS 算经过 1 天，真实距上次核对为 30 天；稳定度/难度不变也不能保证记忆状态不变，下一次计算会失真。
- 修改：独立持久化 FSRS 最近核对时刻（或明确保留它的等价方案），未核对完成和 D11 重排不得改它；同步合法性与投影列。

### F2：D8′ 允许补录，但 FSRS 按真实完成日期调用会发生时间倒流
- 位置：review_progress:87–88、117、134。反例：先推进 10-10 的核对，再到达新的 10-05 核对（不同 completion_id）。
- 库计算 days_since_last_review=-5，进入 `<1` 的短期分支；返回 last_review=10-05，存储层又将日期保留为 10-10，
  记忆参数和记忆时钟不再对应同一次推进。没有按 D8′ 重放，却仍发生计算错误。
- 修改：明确晚到核对的 FSRS 时间规则并保持状态/时钟一致；不能静默把负间隔当同日复习，也不能直接拒绝 D8′ 已允许的补录。

### F3：默认逐字节不变与统一新增投影列的边界矛盾
- 位置：review_progress“选择开关”、config §2.3、learning_state_projection review_items 列表。
- 反例：旧阶梯工作区不写 algorithm，重建投影仍按新规格增加 stability/difficulty 列；SQLite schema 及 SELECT * 输出都会变化。
- 修改：明确投影 schema 升级是否为兼容承诺的显式例外，或规定满足旧输入逐字节不变的分支；不要让实现者同时满足相斥要求。

## 留给最终大检查

- “一律 Review”限于已初始化卡片还原；首次接管的新卡用默认 State.Learning，空学习步使首次处理后进入 Review，避免未初始化字段断言失败。
- M30 §7 决议表、末尾自拟细则及常量注释仍写“间隔”；同步说明 FSRS 看稳定度，舍入边界可能与整数到期间隔不同。
- 明确已存 fsrs 项切回 ladder 的处理，以及 FSRS 卡片 ID/UTC 时刻的确定性与记忆字段有限数校验。
- D11 保留稳定度会保留当前 M30 档位，直至下次核对更新；最终核对页面是否清楚区分稳定度档位与当日回忆概率。

结论：FAIL；修订 F1–F3 后再写实现任务书。专项结论：评分无自评入口，但现稿尚不能保证未核对完成保持完整 FSRS 记忆状态。
