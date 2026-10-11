# 第 217 轮任务书：M18 课表协同规格——只审细则（gpt-6.1-sol）

## 背景

路线图 ④ 课表协同。决策者按用户 2026-09-30 的选择起草了规格 `contracts/timetable.md`（§9 是用户原选项）。
按 `AGENTS.md`"决策者细则先审再实现"，本轮**只审规则本身**：与用户原选项是否一致、边界与反例、
与现有端口（M26 / M8 / M9 / M13 / M19 / M27 / M0）接缝是否会出错。**还没有任何实现代码**。

## 必读

1. `AGENTS.md`（常驻规则、威胁模型、已知缺陷清单）
2. `contracts/timetable.md`（待审草案）
3. `data/personal/schools/<用户学校>.yaml`、`data/personal/timetable.yaml`（个人数据，已移出 git；当时路径不同）（按草案写的真实数据；尚未登记进注册表）
4. 接缝相关：`contracts/availability.md`、`contracts/workspace.md`、`contracts/route_plan.md`（预算解析部分）、
   `contracts/planner_port.md`（输入包 `availability` 字段）、`contracts/freeze.md`（阈值用配置容量）、
   `contracts/day_plan_store.md` §可用时间上限；代码 `ky/availability/port.py`、`ky/schedule/budget.py`、
   `ky/__main__.py` 的 `_preflight_load_context` / `_preflight_calculate`、`ky/planner/port.py` `_build_input_data`、
   `ky/freeze/resume.py` `_capacity_for_day`。

## 请逐条判断

1. **与用户选项一致性**（§9）：计算规则 §4 是否忠实于"扣课取空档再封顶 + 按大节数减上限"；"120 只是默认基数、实际由 AI 裁定"
   是否被 §6.3"课表值不作硬上限"正确表达；有没有把用户没选的东西塞进来。
2. **计算规则的边界与反例**：给出具体输入（学期 / 课程 / 例外 / 规则数值）与草案算出的数字，指出不合理或二义之处。
   至少考虑：跨午休的连堂课；缓冲伸出学习时段；课程重叠；`follow` 指向另一周 / 自己 / 例外日；
   学期边界与学期之间的空档；`weeks` 表达式（`(单)`、`周`、重复、越界）；`cap − b × 扣减` 为负；
   `daily_cap_minutes` 缺省取配置；上限小于空档或反之。
3. **接缝**：`source = "timetable"` 走 `daily_minutes_override` 与 `drop_when_short` 是否会让现有输出在**未登记课表**时改变；
   M19 输入包 `availability` 字段在"只登记课表、未登记手填"时由 `null` 变为对象是否合理，是否需要升输入包版本；
   `ky resume` 跨很多天调用时课表对象只读一次是否足够；冻结阈值不看课表是否与 D11 一致；
   M13 上限只看手填是否留下"课表说 75、AI 声明 200"之类需要护栏的日常问题。
4. **格式**：学校档案与个人课表的字段、校验是否足以让"另一所学校 / 另一个学期"只加数据不改代码（D5 / D6）；
   时刻必须带引号字符串是否合理；`blocks` 划分规则；`unconfirmed`；`source.kind` 枚举是否够用。
5. **可维护性（D7）**：端口划分（M26 定义协议、不 import M18）是否清楚；有没有更简单的等价设计。
6. **转录核对**（可选）：个人课表 `data/personal/timetable.yaml` 内部是否自洽（同一学期内有无重叠课、周次越界）。
   原始 PDF 不提供给你，不要去找。

## 输出

写到 `review/rounds/round-217-m18-timetable-spec-review-sol61.md`：

- 结论：PASS / FAIL（FAIL = 至少一条"必须改"）
- **必须改**：日常使用会碰到的问题，每条附具体输入、草案给出的结果、你认为应有的结果
- **建议改** / **不改**（说明理由）
- **安全登记**（如有，按 `AGENTS.md` 威胁模型单列）

## 禁止

- 不联网；不修改任何文件（只写上面那一份报告）；不跑测试（本轮没有实现可测）。
- 不读用户目录下的任何 PDF 或仓库外文件。
