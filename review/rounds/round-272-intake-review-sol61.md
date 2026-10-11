# 第 272 轮：M32 学完入队与标记坏题实现初检

结论：**FAIL**。一项必须改；269 M1 / M2 已落实。
范围：仅核对指定规格与两包相关实现；未联网、未读个人 / 忽略状态，未复跑真实工作区演示。

## 验证

`PYTHONDONTWRITEBYTECODE=1`：
`py -3.12 -m unittest tests.contract.test_review_intake_port tests.contract.test_question_bank_port`
结果：**25 tests，1.225s，OK，退出 0**；未跑全量。合成文件均在系统临时目录，已清理。

## 指定重点核对

- 269 M1：CLI 用 read_state_sources().items；合成无 manifest 首次 learn 成功，创建 rv-<ID>、introduced_on=10-02、due_date=10-03、fixed_bootstrap / phase=0。
- 批量校验：同一次请求先给有效新点、再给树中不存在的点，退出 2，已有队列各文件字节完全不变。
- --leaves-under：同份合成队列已有一个活动叶子，批量命令跳过并列出它，仅新增另一个叶子，最终共两项；根本身未入队。
- 新项经 validate_review_item 构造；分钟数沿用 1..MAX_SINGLE_PASS_MINUTES，跟踪节点 / 在考校验、显式重复参数处理已接上。
- review_id 分配检查全队列与本批次占用；CLI 汇总成功后调用一次 write，未写完成事件或日计划。
- 269 M2：合成未停用 01–09 时追加 10 被拒；全部停用后追加 10 成功，历史十题保留、未停用仅一题。
- 序号校验已放宽 01–99；停用标记与原题分开，重读校验后 os.link 发布；原题哈希在停用后不变。
- 点名测试覆盖停用 dry-run 无写入、重复 / 不存在题号拒绝、停用跳过、文本提示及历史读取；最近题组边界见 F1。

## 必须改

### F1：最近题组全部停用时仍取祖先题，跳过 §6a 指定的补题分支

位置：ky/question_bank/port.py:350–357 先过滤 retired，再把空组当“没有题”继续上溯；ky/__main__.py:1383 仅在最终无题时检查全部停用。
合成输入：learned 项挂在 `math1.demo.chapter.item-a`；自己的 `qb-math1.demo.chapter.item-a-01` 已停用，父节点 `math1.demo.chapter` 的 01 题未停用。
`adapted_question_group_all_retired(...)=True`，但选择器返回父节点题；10-03 的 review-questions --json 同样返回 `qb:qb-math1.demo.chapter-01`，没有 status / generation_command。
§6a 要求该点（含向上找到的那组）全部停用时按“缺改编题：先生成”处理并注明全部停用；§5 只在自己的题组不存在时向上找。
须先确定最近存在的题组，再过滤停用题；若该组全部停用，应返回上述缺题提示，不能越过该组继续选祖先题。若要改选可继续上溯，须先明确修订 §6a。

## 留给最终大检查

- 文本停用提示缺必填 --date，直接复制会用法报错；提示格式继承规格原文，留规格 / 提示一起完善。
- progressing 真题耗尽后全停用仍显示“缺题”而非 §6a“先生成”，沿用 269 登记的输出优先级问题。
- append_question 两次读取题库、dry-run 与正式写入的容量校验一致性，留最终核对。
