# 评审：WP-E3a 路线包络落盘（合并提交 `36024f9`，实现提交 `8051e22`）

遵守 `AGENTS.md`（不跑全量）。运行用 `git archive <合并提交>`（原始资料与 `products` 空目录照前几轮补）。

范围：`git diff <合并提交>^1 <合并提交>`；任务书 `review/rounds/round-97-wp-e3a-task.md`；实现者报告 `review/rounds/round-97-wp-e3a-luna.md`；
新规格 `contracts/route_plan.md`。决策者审查时改了三处：锁冲突的错误路径改为锁文件并在规格写明崩溃残留锁由用户手动删除；
`_routes_store_path` 改用 `_load_workspace_for_default`；测试改为解析 YAML 删除 `state.routes` 而不是替换文本。

请判断：
1. 格式：`parse_route_plan` 与 `route_plan_to_mapping` 是否互逆、严格（键、类型、日期、非有限数）；错误路径是否精确；是否有经 YAML 可绕过 `validate_route_plan` 的输入。
2. 存储：版本比较并交换是否真正阻止跳号 / 旧号 / 换 `route_id`，拒绝时是否一字节不写；锁的取舍（实现者自加，任务书未要求）——残留锁的代价与手动恢复是否可接受；
   版本文件"不覆盖"在 `os.replace` 下是否成立；manifest 被篡改或结构异常时是否 fail-closed（例如 `revision` 非整数、条目乱序、`path` 越出存储根）。
3. CLI：退出码、`--store` 缺省、`show --json` 形状与规格一致；`submit` 失败时不留文件。
4. 注册表新增 `state.routes: data/routes` 对其他模块与测试的影响。
5. 新测试撤实现是否变红。

产物：`review/rounds/round-99-review-sol-out.md`，每项"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
