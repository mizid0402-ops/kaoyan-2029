# 续：评审被中断，范围调整

宿主会话重启，你上一轮评审（`review/rounds/round-52-h2-wpc-review-sol.md`）在写产物前被终止。同时用户做了新决议（`docs/阶段2.5-接缝收口.md` §七）：
**D8 已被 D8′ 取代**（复习次数不设上限，每次复习都计算；按 `completion_id` 保证同一条记录只算一次），WP-C 的队列部分马上会按 D8′ 重写。

所以本轮只评审：
1. `git show 00398b0`（WP-H2 科目档案）——原第 1 问全部。
2. `git show 57dc49c` 里与 D8 **无关**的部分：自评写回 `last_self_rating` 与裁剪核 tie-break、outcome→质量映射移入 `LadderSm2Algorithm`。
   D8 相关（同日冲突、out_of_order 跳过、CLI 冲突预检）不用审。

主工作区另有 luna 在改 `ky/knowledge/` 等文件；需要跑测试时只跑相关单模块，若受中间态影响请注明。不跑全量。
产物：`review/rounds/round-52-h2-wpc-review-sol-out.md`，每条 "必须改 / 建议改 / 不改"，给 PASS / FAIL。
