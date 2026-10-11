# 第 259 轮：M30 掌握度规格初检 — FAIL

范围：`contracts/mastery.md` 全文、`contracts/charts.md` §8及点名接口；只静态阅读，不写代码、不跑测试。
未联网、未读个人数据或 gitignore 学习状态；仅新增本报告。

## 已确认

- 四档间隔门槛 7/30、多项取最低及最近祖先继承，未发现与用户档位选择直接冲突。
- 薄弱判据采用所选复习项组中任一 `lapses >= 2`；排除暂停/退役是明确的自拟统计口径。
- `ReviewItem.state/schedule`、`ReviewSchedule.interval_days/lapses`、四种 `VALID_REVIEW_STATES` 均存在。
- M4 公开 `tree_parent(point_id, points_by_id, grammar)` 存在；M28 `PacingSettings.start/exam_date` 存在。
- 权重形状确为 `topic_weight[subject_id][node_id] -> number`（`contracts/topic_weights.md:95`）。

## 自评路径专项确认

- 合法队列间隔为 1..180（`ky/models.py:728`）；`check=none` 得到 quality=None，不进入核对推进分支。
- strict：四档自评及缺省均保留 interval；lenient：unknown→1，vague→max(1, interval//2)，其余保留。
- 因此现有 `LadderSm2Algorithm` 两档均无未核对完成拉长 interval 的路径；v1 quality 也解析为 check=none。
- 依据：`completion.py:104–124、165–170、348–354`，与 `review_progress.md` 推进表一致；此项通过。

## 必须改

### M1：§4“有考频权重就加权”与数学一、英语一等权选择冲突
- 现有 `topic_weights.json:123、164` 分别已有 math1、eng1 权重，不能把“有该科权重键”当作启用条件。
- 反例：数学两个等权叶子，一巩固一未学，文件对应权重 9/1；按通用句能力为 0.9000，用户等权要求为 0.5000。
- 修改：明确权重启用策略与调用方何时传 weights=None；由显式策略驱动，不能只凭文件中有键启用，也不新增写死科目分支。

### M2：§5 混合日期与 null 能力值没有运算边界
- 反例①：旧路线起于 2026-01-01、考试 2027-01-01；新复盘设置 start=2027-01-01、exam_date=2028-01-01。
  两份来源各自合法，规格选出的 start=exam，线性公式除零；start 晚于旧路线考试时还会产生反向时间比例。
- 反例②：§4 明确支持总权重为 0、ability=null；§5 仍要求“能力值−应完成度”，不能对 null 做减法或当作 0。
- 修改：运算前定义 exam<=start 的处理（契约错误或无目标及原因），并定义空能力科目的差距为 null、保留其他科目计算。

### M3：M30 输出不足以落实 charts §8 的“遗忘次数”列
- 反例：叶子继承同一祖先的两项，lapses 分别为 2、5；M30 仅输出 weak=true，无次数或所选项身份，M17 无法确定应显示多少。
- 修改：在叶子映射输出所选项组的遗忘次数，明确多项聚合规则，并由同一映射供应薄弱表格；不能让渲染层重推导一套口径。

## 留给最终大检查

- §1“只有答对才变长”不准确（partial=3 也推进）；charts“自评不参与”应说明 lenient 可缩短间隔、降档，但不能提级。
- 四档独立 HALF_EVEN 舍入至四位后不保证和恰为 1（各占 1/3 的三档合计 0.9999）；明确精确值与展示值的区别。
- 章权重均摊、零权重单列、能力仅取巩固占比与全巩固目标属于代理指标细则；最终核对页面解释、缺树及空科目展示。

结论：FAIL；先修 M1–M3，再写实现任务书。
