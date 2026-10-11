# 评审任务书：第 173 轮 —— WP-G3h 返工（你第 172 轮的 M1 / M2，窗口 `sol-main`）

请复审 `luna-a` 第 173 轮。任务书 `review/rounds/round-173-g3h-fixes-task.md`，
实现报告 `review/rounds/round-173-g3h-fixes-luna.md`，你上一轮的报告 `review/rounds/round-172-g3h-tools-review-codex.md`。
决策者对 M2 的裁定写在任务书第二部分：两支 `round*_validate_*` 保持 `validation` 分类，照规则补拆。

**本轮范围**：`tests/test_tools_split_baseline.py`、`tools/round24_validate_weighted_tree.py`、
`tools/round29_validate_agreement.py`（`git diff 58f44bc -- <这三个文件>`）。
`tests/contract/test_exam_index_port.py` 是另一个窗口在做的第 176 轮，**不在本轮范围**。

## 重点看

1. **M1**：在不补 `review/408知识点树与真题` 产物的干净归档里，模块是否不再失败；
   HTML 成功路径是否真的在临时产物根里运行并逐文件比较，而不是被跳过；
   验证器成功场景缺产物时是否**只跳过它自己**，提示是否写明缺什么、如何恢复；
   原来同一方法里的 NETEM 等对照是否仍在干净归档里运行。
   "工作区代理只替换 products 根"这一做法是否让新旧两版读到的是同一份输入、比较的是同一份输出。
2. **M2**：两支 `validate` 拆分是否纯移动——检查项、顺序、`continue` 条件、错误消息、返回值不变；
   对照基线确为 `58f44bc` 的旧长函数；失败路径是否真的触发了声称的那段检查。
   round24 成功路径在本机因缺来源缓存而跳过——请判断它的失败路径覆盖是否足以证明拆分未改行为，
   必要时自己加一条不依赖外部资料的变体探针。
3. 自己做一次定点变异（例如调换 round24 两个辅助的调用顺序），确认对照变红。
4. 按 README 状态再扫一次：`active` / `validation` / `acquisition` 脚本中无函数超过 60 行。

## 规则

只跑与结论直接相关的单个模块或单条命令，**不跑全量**；复现用系统临时目录，不写进仓库。
结论 PASS / FAIL，分"必须改 / 建议改 / 不改"，每条附可复现输入；安全类单列"安全登记"。

## 报告

`review/rounds/round-177-g3h-fixes-review-codex.md`。
