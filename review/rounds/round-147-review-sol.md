# 复审 F-b（`74ec415`）＋ 评审 WP-F-c（`ec832c7`）

遵守 `AGENTS.md`（不跑全量；严重度按威胁模型，安全类单列）。用对应提交的 `git archive`（补原始资料与 `products` 空目录；`git show` 基线用 `GIT_DIR`），只在你自己的临时目录运行；变异时设 `PYTHONDONTWRITEBYTECODE=1`。

## 一、F-b 复审：`74ec415`

你第 142 轮 B1：`record` / `resume` 的队列变更没从投影读回核对。请重放你的"`due_date` 写成常量"探针，并试一两个别的列（例如 `schedule_*`、`state`）确认也会被抓到。

## 二、F-c：`ec832c7`

依据：你第 142 轮第二部分的最终规则 1–4；任务书 `review/rounds/round-145-wp-fc-task.md`；实现者报告 `round-145-wp-fc-luna.md`（第二节）；规格 `contracts/projection_status.md`、`contracts/state_snapshot.md`。
请查：M12 计数函数与快照输出逐字节不变（含零项科目、边界日）；`status_as_of` 由投影行重建 `ReviewItem` 是否与队列原对象完全一致；M12 与 M15 在同一数据同一日期是否必然同数；冻结 JSON（`frozen`、仅冻结时 `resume`）；
`as_of` 含义在规格 / CLI 文案里是否写清且没有"实时 / 已反映刚才写入"的说法；只读打开、不建空库；schema 2 / 缺表 / 配置外科目 / 缺配置的错误；旧重建命令输出与 `b867ae7` 一致；有没有建议 / 推荐语义。

产物：`review/rounds/round-147-review-sol-out.md`，两部分分节，"必须改 / 建议改 / 不改"附可复现输入，"安全登记"，各给 PASS / FAIL。只写这一个文件。
