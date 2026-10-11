# 第 268 轮：A + B + C 与 M31 实现初检

结论：**FAIL**。两项必须改；其余指定重点在本轮核对范围内通过。
范围：指定规格、相关改动片段、三条数学一抽查与合成输入；未通读全部代码、未评视觉、未跑全量。

## 验证

`PYTHONDONTWRITEBYTECODE=1`，执行任务书指定命令：
`py -3.12 -m unittest tests.contract.test_question_bank_port tests.contract.test_mastery_port tests.contract.test_route_plan_port`
结果：**37 tests，4.741s，OK，退出 0**。合成文件仅在系统临时目录，均已清理。

## 指定重点核对

- 264 M1：真实公开端口 `candidate_check_questions` 已扩展；合成叶子无映射、祖先有题时回退正确，`include_details` 同时给出题型 / 分值 / 答案。
- 264 M2：每题一文件，临时写入、重读、`os.link` 发布；合成追加 01–03 后共三文件，01 原始字节哈希不变。
- 264 M3：选题函数及点名测试验证未用题优先、第三题可轮到；命令的历史引用装配仍有 F1。
- 264 M4 / M5：合成无真题的非叶子章节点生成 `basis: syllabus`、含后代条目、`based_on: []`，引用字符串日期时正式提交成功；模板日期另见 F2。
- 按档位出题：同一输入中 FSRS stability=3 返回 adapted / exercise，stability=7（interval_days=1）返回真题 / past_question，按稳定度切换正确。
- A：FSRS stability=30、interval_days=1 的同一项，未真题答对为 progressing，答对过为 consolidated；能力页调用层仅收集 past_question + correct 的 review_id。
- B：1 月 11 日目标 50/20、21 日目标 100/80；16 日应到 0.7500/0.5000，当前 0.8000/0.3000 时两差距为 +0.0500/-0.2000。
- M28：合成 1 月 6 日切段后前半 targets=None，原末端目标留后半，后续阶段目标保留，应到值不变；原地替换片段也保留 targets。
- 无 targets 的 v2/v3：固定基线 `cfd573e657ef4aa8ee6562ff0cd8e7f0a399158d:ky/schedule/planning.py` 与当前映射接口在同份合成路线上的 YAML 字节一致。
- M17 双差距字段与渲染分支接上新版 M30；workspace 登记、题库写入目标与提示中的 guided 限制已落实。

## 包 C：三条抽查

- `math1.pr.ch21.requirements.item-03`：标题修成“相合性”，2026 quote_ref 保留原“柑合性”，旁置报告登记修正（264 M6）。
- `math1.pr.ch15.requirements.item-03`：保留 2026“概率计算的方法”；2022 quote_ref 保留旧措辞，未把确认变更当错字改回。
- `math1.hs.ch01.requirements.item-02`：普通条目标题与两源一致。
- 三条均为 scope=item、status=extracted；六个来源 quote_ref 经现有验证器的去标签 / 空白归一口径均定位成功，六处 SHA-256 均匹配。
- named_chapters 新增 requirements.item-NN 约束；钉住的节点 / scope 数量更新位于数据清单测试。未额外运行树验证命令或其他测试模块。

## 必须改

### F1：规格的 `qb:` 引用未被命令历史读取识别，正常记录会重复选已做题

位置：`ky/__main__.py:1203` 只识别 `startswith("qb-")`；`:1256` 又输出裸题号，未按 M31 §1 输出 `qb:<题号>`。
合成输入：题库 `qb-math1.demo.chapter.item-01/02/03`；low 项 stability=3；9 月 28 / 29 日的 exercise + correct 完成分别引用 `qb:qb-math1.demo.chapter.item-01`、`qb:qb-math1.demo.chapter.item-02`。
执行 `review-questions --date 2026-10-01 --json`：退出 0，却返回第 01 题；按规格应返回尚未做过的第 03 题。
须统一规范输出与历史引用解析，把规格形式转换为存储题号后参与 uses 轮转；不能仅让选题函数在裸 ID 的测试里通过。

### F2：照规格 / AI 提示的未加引号日期提交，会契约报错退出

位置：`ky/question_bank/port.py:96` 仅接受 str；规格 §3 与 `prompts/adapted_questions.md` 示例均是未加引号的 `created_on: 2026-10-01` / 同类日期。
合成输入：由合法无真题非叶子输入包生成的题目，basis=syllabus、based_on=[]、input_hash 正确，仅将 created_on 写成上述示例形状。
`submit_staged_question` 实际报 `proposal.yaml.created_on: expected an ISO date (YYYY-MM-DD)`；CLI 捕获后退出 2。同题将日期加引号即提交成功。
须支持示例所示 YAML 日期并归一为 ISO 字符串，或明确字符串约束并同步规格 / 提示示例，避免正常 AI 产物必然被拒绝。

## 留给最终大检查

- 改编题最近使用日期当前取 event.day；补录时与 completed_on 不一致的轮转口径，留最终核对。
- 祖先候选全被 exclude 后的上溯策略、粗粒度真题通过向后代继承及 content/item 同时计数，沿用 264 登记。
- 包 C 其余条目、公式缺漏与旁置差异记录，以及旧构建器覆盖新树的使用提示，留最终核对。
- 路线规划 AI 指引尚未补阶段目标句（267 报告称无对应文件），留最终核对。
