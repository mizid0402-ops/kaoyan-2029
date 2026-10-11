# 第 225 轮任务书：M29 课表导入 / 导出规格——只审细则（gpt-6.1-sol，续 sol61-m18）

## 背景

路线图 ④b。决策者按用户 2026-09-30 的选择起草了 `contracts/timetable_import.md`（§8 是用户原选项与决策者拟定项）。
④a（M18，`contracts/timetable.md`）已提交 `4816a14`；本轮**只审规则本身**，还没有实现。

决策者本机对一份真实正方 PDF 做过可行性探针（结论已写进 §4：星期标签沿一条轴等距排列、版式旋转、课程文字跨行跨页、
星期标签只在第 1 页）。真实 PDF 是个人数据，不提供给你，也不要去找。

## 必读

`AGENTS.md`；`contracts/timetable_import.md`；`contracts/timetable.md`；`contracts/workspace.md` §2.6、§4；`contracts/planner_port.md`（staging 路径规则与规范 JSON 哈希）；
代码 `ky/timetable/`、`ky/storage/atomic.py`、`ky/planner/port.py`（staging 路径包含检查的写法）。

## 请逐条判断

1. 与用户选项一致性（§8）；决策者拟定项是否合理。
2. ics 导入（§3）：给出具体 `.ics` 片段与参数，检查展开、时区、`RECURRENCE-ID`、`EXDATE`、对回节次、定周次、分组合并的边界与二义；
   哪些真实课表导出（逐次事件 / 每周重复）会被误拒或误收。
3. PDF 解析（§4）：星期带判定、排序连接、记录切分、核对规则是否足以"要么正确、要么明确报错"；有没有静默丢课或串课的路径。
4. apply（§5）：追加 / 替换 / 校验 / 备份 / 规范重写的顺序与中断后的状态（`AGENTS.md` 已知缺陷第 1 条、日常中断属必须改）。
5. 导出（§6）：确定性、浮动时间、UID、与 M18 结果一致性；有没有日历应用常见的兼容问题需要写进规格。
6. 个人数据边界（§1、§2）与 D7 可维护性（两层解析、适配器可替换）。

## 输出

`review/rounds/round-225-m29-timetable-io-spec-review-sol61.md`：PASS / FAIL；必须改（附具体输入、草案结果、应有结果）/ 建议改 / 不改；安全登记单列。

## 禁止

不联网；只写这一份报告；不跑测试；不读仓库外文件；报告里不写任何个人数据。
