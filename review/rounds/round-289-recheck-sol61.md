# 第 289 轮：11 条必须改独立复验（sol61）

## 1. 结论：FAIL

10 条已修好；C-M1 部分修好，记录写入仍重复读取来源。另有一项基线例外校验过宽，违反本轮明确验收要求。
已读 AGENTS.md、281–283 原报告、284–288 修复报告及五个指定提交；仅评审修复与直接影响。
仅新增本报告；不改实现、测试、规格或其他文档，不提交、不联网、不读忽略的个人数据。
合成输入及探针在系统临时目录；全部 Python 执行使用 PYTHONDONTWRITEBYTECODE=1 / py -3.12 -B。
全量：未跑（按 AGENTS.md，由决策者提交前统一跑）；用户提供的 1145 tests 结果不作为本轮独立运行结果。

## 2. 11 条逐条核对

以下 P 指系统临时目录 `round289_probe.py`；每项使用一个组合探针或一个代码位置。

| 项目 | 结论及最小证据 |
|---|---|
| A-M1 | 已修好。P.a1：UID cut-duration / DURATION:PT45 → 公开入口 ContractError，含 UID cut-duration.DURATION；真实 CLI 退出 2，暂存 YAML 0 份。 |
| B-M1 | 已修好。P.charts：三个 None 分别抛 ContractError，路径 week.days / progress.start / ability.today；七日周图、合法进度/能力映射与 0ad2b53 的父提交结果相等。 |
| B-M2 | 已修好。P.bank_cases 取得实际 CLI 提示；PowerShell Language.Parser 解析命令部分，parse_errors=0；原因带引号、日期保留。 |
| B-M4 | 已修好。P.bank_cases：同目录合法题号的题目/停用临时名（含 p_1q2r3s）被跳过；manual-notes.txt、别的知识点临时名、7 位后缀、00 题号均 ContractError。 |
| B-M5 | 已修好。P.bank_cases：已有 01 后 append 02，Path.open 读模式计数，已有题目 YAML 只读 1 次；序号与容量共用解析结果。 |
| B-M6 | 已修好。P.bank_cases：已有 01/02，新鲜输入包重复提案 02；dry-run/正式均报 expected next question id …-03，库内文件前后完全相同。共享预检见 ky/question_bank/port.py:242。 |
| B-M3 | 已修好。P.bank_cases：interval=7、空真题索引、自己的改编题全停用；CLI JSON 为 progressing，包含“先生成”“已全部停用”及 planner-input 生成命令。 |
| C-M1 | 没修好（部分修好）。P.source_counts：有当日事件的 load_today 中索引、权重、manifest、每片、树各 1 次；record_day 中旧 manifest / 每个旧分片各 3 次。schema_version 仍为 1，映射字段未变；60a4fd2 CLI 矩阵及记录产物对照通过，基线测试例外缺陷另见 M2。 |
| C-M2 | 已修好。P.freeze_cleanup：达冻结阈值，仅 freeze 临时文件 unlink 抛 PermissionError，并让完成事件写失败 → stage=freeze_written、冻结 1 条；发布前 os.link 失败仍抛 StorageError、冻结 0 条。ky/storage/day_plan_store.py:208 按 published 布尔值区分阶段。 |
| C-M3 | 已修好。P.pending_and_exception 的渲染分支：pending 同时含已存 correct 结果、补推进提示/按钮；None 为“未填写”，0 为“0 分钟”。ky/web/server.py:211 保留明确空值判断。 |
| C-M4 | 已修好。ky/today/port.py:3 明列 load_today、today_view_hash、record_day、advance_recorded_day。 |

## 3. 两件额外确认

- 新端口为加法：M24 原 candidate_check_questions 签名保留；M28 missing_report_cycles 原签名保留并委托新加载器；M13 两处 source_state 为可选关键字，旧调用省略仍工作；ReviewQueueStateSources 新字段有默认值，旧两参数构造仍合法。
- 旧调用证据：CLI 固定矩阵、题库生成/提交探针、M24 祖先候选单测、M13 重放及 schema-1 混合队列拒绝单测均通过；ky/charts 继续只消费 items/sources。四份规格已同步：check_questions.md:16、pacing_review.md:61、day_plan_store.md:193、state_sources.md:31。
- 固定基线：today.md §6 确实只列恢复命令行与原因占位符两处；event_written 单测精确比较旧 stderr + 预期恢复命令，其余输出/产物逐字节比较。但停用提示 helper 放过整行其他变化，不能确认“只允许原因占位符变化”，见 M2。
- 实际点名单测：CLI 基线矩阵、event_written 例外、网页/CLI 记录产物对照：3 tests / 28.134s / OK；M24 祖先候选、M13 重放、schema-1 拒绝、今日映射上下文：4 tests / 0.199s / OK。

## 4. 必须改

### M1 / MAJOR：C-M1 记录写入没有贯彻来源一次读取

- 位置：ky/storage/day_plan_store.py:532 未向写端传来源；ky/storage/review_shards.py:630 再读 manifest，:646/:661 再读旧 manifest 和旧分片（分片自身又读字节和 YAML）。这些是旧输入，非临时输出校验。
- 唯一探针：P.source_counts；合成两条同科 progressing 项、空登记索引/权重、知识树及前一日事件，次日 record_day 提交两项 correct。旧 manifest 与两个旧分片分别都是 3 次；索引/权重/树各 1 次。
- 复现：`py -3.12 -B -c "import sys; sys.path.insert(0, r'C:\Users\Lenovo\AppData\Local\Temp'); import round289_probe as p; p.source_counts()"`（先设 PYTHONDONTWRITEBYTECODE=1）。
- 要求：已加载队列来源继续贯穿实际存储写入所需的旧状态比较；M33 单次 record / advance 不重开旧来源，保留旧调用方行为及临时输出重读校验。按原 C-M1 与 AGENTS 已知缺陷 #2 判必须改，未用并发探针推定数据损坏。

### M2 / 验收必改：停用提示例外没有限定为占位符替换

- 位置：tests/contract/test_today_port.py:625–629 只确认两个原因子串，再以整条 old_line 替换 new_line；题号、日期、命令前缀或该行尾部的其他差异均被抹掉。
- 唯一探针：P.pending_and_exception 中向 helper 传同一停用行的 old/new；new 同时换带引号占位符并把日期 2026-10-01 改为 2099-01-01，helper 仍通过。该日期差异不在 today.md §6 的两项例外内。
- 复现：上述导入命令最后改为 `p.pending_and_exception()`；期望非允许日期差异触发 AssertionError，实测被接受。
- 要求：断言 new_line 恰为 old_line 的指定原因占位符替换，保留题号、日期、命令文字及换行的逐字节比较；不能仅检查含目标子串。

## 5. 建议改

- 无新增；沿用原报告建议，不扩大本轮修复范围。

## 6. 安全登记

无新增；沿用既有登记。M1 是明文来源读取要求未完成，M2 是验收比较范围错误，均不归入攻击登记。

## 7. 最坏情况

已确认：正常记录仍重复解析旧队列；现有基线 helper 会漏报停用提示同一行的日期等回归。
合理推测：重复读取期间来源若变化，仍可能混合旧状态；本轮未证实数据损坏，不把跨进程竞态另列必须改。
当前正常成功记录/重放对照通过，发布后清理故障阶段正确；这不替代 M1 的一次读取验收，也不证明 M2 可拒绝非允许差异。
未复验个人输入、原报告建议或视觉布局；初版探针图表字段不全及冻结未达阈值已校正，不算实现缺陷。
