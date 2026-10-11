# 第 282 轮：最终大检查 B

## 1. 结论：FAIL

发现参数护栏、停用提示、缺题输出、中断恢复及提交预检问题；下列必须改集中交回。
已按任务书顺序读规则、模块地图、规格、历史关闭项与交接 §10；不重复报告已关闭缺陷。
未联网、未读取忽略的个人数据、未改实现/测试/规格、未提交；合成输入均在系统临时目录。
设置 `PYTHONDONTWRITEBYTECODE=1`，仅运行直接相关模块及下述定点探针。
`py -3.12 -m unittest tests.contract.test_mastery_port tests.contract.test_charts_port`：12 tests，OK。
`py -3.12 -m unittest tests.contract.test_question_bank_port tests.contract.test_review_intake_port`：26 tests，OK。
`py -3.12 -m unittest tests.contract.test_fsrs_algorithm_port tests.contract.test_check_questions_port`：22 tests，OK。
全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。测试通过不覆盖下面的反例。

## 2. 逐条回答

- A1 已核实：合法 FSRS 项 stability=30、无真题通过记录，`item_level(item, False)` 为 progressing；阶梯边界也由已运行的 mastery 测试覆盖。
- A2 已核实：合成等权三叶分别 learned/progressing/consolidated，展示占比各 0.3333，Decimal 合计 0.9999。属展示舍入；当前 mastery §4 已明示允许偏差，不违反契约。
- A3 已核实：零权重与空树的占比/能力为 null；缺树映射保留科目、树卡写“无知识树”。`ky/charts/cli.py:246` 按 feature 选加权科目，其余传 None；登记表仅 cs408 开启。空值文字仍有建议。
- A4 已核实：`ky/mastery/port.py:35` 不读自评；`mastery_gap` 只读路线目标。已运行档位及 FSRS D9 测试，自评不能提级或抬高应到；阶梯 lenient 可降档。
- A5 已核实：无路线为 missing_route，无 targets 为 no_targets，两者 expected=null；目标 consolidated<=covered 的护栏在 `ky/schedule/planning.py:165`，由 M30 调路线校验。
- B1 已核实：固定同一合成队列，配置省略→ladder→fsrs→ladder：省略与显式 ladder 包哈希相同，fsrs 改变哈希，切回恢复原哈希及同输入推进的队列字节。
  接入前固定提交 `1c00c00c6d869eaa498150b1608b01e09f14d1d1` 与当前省略开关：包字节/哈希、队列文件字节、成功 preflight 的 stdout/stderr 均相同；各命令退出 0。已推进的状态发生变化时不承诺哈希恢复；实际 fsrs→sm2_lite 的字段清除由点名 FSRS 测试核实。
- B2 已核实：同一 stability=30、真题通过项 reset 后 interval=1、stability=30，档位仍 consolidated；符合 review_progress 的“保留记忆字段”，不是回忆概率保证，页面解释见建议。
- B3 已核实：`ky/schedule/fsrs_algorithm.py:110` 固定 card_id=1、UTC 零点、关闭 fuzzing；确定性测试通过。合成 stability/difficulty 的 NaN、inf、负值均被拒，错误带 schedule 字段路径。
- B4 已核实：已运行 `test_unchecked_d9_keeps_memory_state_and_caps_unrated_interval`；strict 保持，lenient unknown/vague 仅缩短，basic/fluent 保持，记忆字段不变。
- C1 不成立（护栏部分）：映射无文件/状态写入，但三个端口缺少先校验后运算；合成非法参数直接抛 TypeError/AttributeError，探针见 M1。
- C2 已核实确定性；不成立（文件名唯一性）：三页重复渲染测试通过；合成学期 term/a 与 term a 均成功写 week--term_a--w01.html，后者覆盖前者。符合当前文件名规则，列建议修订规格。
- C3 已核实：当前图例取科目中文名；零分钟计划仍画图，分钟全缺省写“未记录”。`test_progress_render_daily_tiles_order_and_weekly_empty_states` 已运行，255 登记的误导文字已消失。
- C4 已核实文字，阅读效果属于判断：`ky/charts/render.py:354` 解释稳定度、锚点与自评；图例区分学过/掌握中/已巩固，薄弱表列遗忘次数，目标写“应到”。未解释真题门槛、D11 保留档位及稳定度不等于当前回忆概率，建议补充。
- D1 已核实：`ky/question_bank/port.py:233` 临时写入、重读、os.link 发布，已有目标不能被覆盖；只写一次测试通过。强制终止遗留临时文件另见 M4。
- D2 已核实：题库仅 guided、记录为 exercise；统计/预测输入仍取登记真题索引（`ky/projection/__init__.py:107`），不读题库。M30 单靠改编题核对封顶 progressing（A1）；不替用户验证答题声明真实性。
- D3 部分不成立：停用标记也用 os.link（`ky/question_bank/port.py:303`）；最近题组先确定再过滤，停用题不再选出。提示已带日期，但裸 <原因> 在 PowerShell 无法解析，见 M2；不是重报旧的缺日期问题。
- D4 已核实取 event.day（`ky/today/questions.py:34`），不是 completed_on。合成题 02 在 10-01 完成、归入 10-10 事件，题 03 在 10-05 完成/归档：当前选 03，按完成日期应选 02；规格“最近引用日期”未明确两者，列口径建议。
- D5 已核实：同输入同输出；父链并入后代真题；先找到有来源的祖先，再 exclude，不继续上溯。合成近章 q1 被排除、根另有 q2，返回空候选且 matched_ancestor=近章、fallback=null，符合 §6 当前顺序。改编题组在过滤停用前确定，272 必须改未复发。
- D6 已核实：粗粒度复习项真题答对向后代继承，符合 mastery §3。合成 named_chapters 的 content 与 requirements.item 各自为叶子：只入队 item 时覆盖 0.5000；章项 interval=30 且真题通过时两叶均 consolidated。属于统计粒度决策，非实现漏计。
- E1 已核实：`ky/__main__.py:641` 先汇总各科整批校验，直到 :662 才调用一次 write；坏 ID 在此之前抛错，未写前面有效项。manifest 是生效提交点（`ky/storage/review_shards.py:789`）。
- E2 已核实：`ky/review_intake/__init__.py:74` 全队列占用集，:100 并入本批 ID；跨知识点 retired 项占用 rv-<新点> 的合成探针分配了 -2，活动重复入队测试通过。
- E3 已核实：次日到期；整数分钟只接受 1..MAX_SINGLE_PASS_MINUTES。实际探针接受 1/上限，拒绝 0/上限+1/1.5/bool；leaves-under 跳过活动叶、空结果违约由点名测试覆盖，显式重复参数退出 3。
- E4 不成立：合成 progressing 项无可用真题，自己的改编题组全部停用，实际输出“缺题（该点改编题已全部停用）”，无 generation_command；见 M3。
- E5 已核实：M32 经 read_state_sources 把缺 manifest 读为空队列，首次入队测试通过；与 A 包缺库语义同项，不另开缺陷。

## 3. 必须改

- M1 参数护栏缺失：`ky/charts/data.py:20`、:204、:322。一个合成参数探针分别传 week.days=None、progress.start=None、ability.today=None；实际为 TypeError、TypeError、AttributeError。三个公开数据端口须在运算前校验参数及必要映射字段，并给带参数路径的 ContractError。
- M2 停用提示无法复制运行：`ky/__main__.py:1288` 的 `--reason <原因>`。单探针用 PowerShell Language.Parser 解析该命令，返回 RedirectionNotSupported（“< 运算符保留”）。为原因占位文字加引号，并说明替换原因；保留已修好的日期。
- M3 全停用分支优先级违反 §6a：`ky/today/questions.py:73` 只给 learned 生成指令，:80 的 progressing 分支漏掉。复现：interval=7 的活动项，登记空真题索引，自己唯一改编题已 retire，运行 review-questions --json；结果见 E4。全停用时两档均应提示“先生成”、注明停用并给生成命令。
- M4 中断后整个题库被残留临时文件阻断：`ky/question_bank/port.py:150` 遍历所有文件，:157 拒绝非 YAML，而 :223/:293 正是在库内创建 .tmp。复现：合法题库中留下与写入器命名一致的 `.qb-<ID>-01.yaml.interrupted.tmp`，内容为合法题目字节，load_question_bank 抛“unexpected file in question bank”。强制终止可正常产生此状态；读端应识别自身临时产物并可恢复，保留题目/停用标记只写一次。
- M5 同份题库读取两次：`ky/question_bank/port.py:198` 与 :210 连续 load_question_bank，中间另扫文件名取序号，违反 AGENTS 已知缺陷 #2。保存一次解析结果，从该结果推导序号和可用容量；无需增加并发防护设计。
- M6 dry-run 未校验实际入库条件：`ky/question_bank/port.py:514` 提前返回，跳过 append_question 的序号/容量规则。单探针：已有合法 01 题，用新鲜输入包再次提案 01；dry_run=True 成功，正式提交却报 expected next question id …-02。应抽出共享的只读入库预检，使 dry-run 与正式路径一致，dry-run 不写库。

## 4. 建议改

- C2 修订学期文件名规则，采用可逆编码或可读唯一序号；目前分隔符/空格/中文容易归一为同名，覆盖的是可重建页面，暂不按状态数据丢失判必须改。
- A3 总权重为零时 shares 是“全 null 映射”，`ky/charts/render.py:376` 只判断 shares=None，画空条；明确展示“无可用权重”，空树与缺树也应分别说明。
- C4 说明“已巩固还须曾真题答对；稳定度不保证今天答对；D11 重学只重排到期日”；将“自评不参与”细化为“不能提级，阶梯 lenient 可降档”。
- D4 明确最近使用按完成日还是归档事件日；建议取 review.completed_on，避免补录把早做题误当成最近做过。
- D5 当前不继续上溯符合规格；若要扩大耗尽后的来源范围，先决定是否允许跨章，再修订 §6，不能直接把现状算成错误。
- D6 决策者确定 content 摘要叶与 requirements 条目是否都作独立学习单元；若只学考试要求，应先调整树/统计端口口径，再改变分母。
- 后续修复只补对应缺陷的定点验证，不扩大到全量或其他模块。

## 5. 不改（说明）

- 四档展示和 0.9999、非加权科目的等权路径、无 targets 不显示应到、D11 保留 FSRS 档位：均符合当前明确规格。
- 粗粒度通过继承、近章候选耗尽后退回改编题：当前契约允许；粒度/回退范围属于决策，不擅改算法。
- 255 的 daily_totals、268 的 qb: 引用/日期、272 的最近停用题组、259/261 必须改与 263 引用清单不重复开项。

## 6. 安全登记

本轮未新增经确认的恶意注入/链接攻击结论；未开展攻击探针。M4 属正常强制终止后的恢复问题，不能归入安全登记而免修。

## 7. 最坏情况

已确认：一次题库写入被强制终止后，残留 .tmp 能令全部题库读取及正式提交报契约错误；学习队列/原题不会因此被改写。
已确认：全停用时缺少补题指令，复制停用提示又遇 PowerShell 解析错误；dry-run 可给出无法正式入库的通过结果。
合理风险判断：粗粒度继承与重叠叶子粒度可能同时高估“巩固”或低估覆盖；代理指标需解释清楚，不代表考试能力已验证。
