# 评审：WP-G2a CLI 小项（`2574199`）

遵守 `AGENTS.md`（不跑全量；严重度按威胁模型，安全类单列"安全登记"）。运行用 `git archive 2574199`（照前几轮补原始资料与 `products` 空目录）。
依据：任务书 `review/rounds/round-127-wp-g2a-task.md`；实现者报告 `review/rounds/round-127-wp-g2a-luna.md`；提交信息里写了决策者的改动
（换掉实现者用 `removesuffix(" (selected via ...)")` 拼旧报错文字的写法，恢复 `_plans_store_path`，新增 `_optional_workspace`）。

注意：另一个实现者此刻正在主仓库做 WP-G2b（`tools/` 分层），请只在你自己的临时归档里运行，不要读写主仓库工作区。

请查：
1. 除顶层 `-h` / `--help` 与 serve 多出的一行外，所有 `ky` 调用（每个子命令、无参数、未知参数、`preflight -h`、`--date ... -h`）输出与 `0c3b3e5` 逐字节一致；对照测试是否真按原始字节比较、基线是否固定。
2. `day-plan record`：注册表找不到 / 无效 / 有效三种情况下，冻结锁存、出题建议与两处提示与基线一致；一次 record 里冻结与出题是否确实用同一份注册表；`--store` 有无两种情况。
3. `SUBCOMMANDS` 表：加一个子命令是否只改一处；表里 `preflight` 与"无子命令即 preflight"的关系。
4. serve 地址行（IPv4 / IPv6 / 数据库不存在时不打印）。
5. 新测试撤实现是否变红（决策者已验：把"无效"当"找不到"时两条变红）。

产物：`review/rounds/round-130-review-sol-out.md`，"必须改 / 建议改 / 不改"附可复现输入，"安全登记"一节，最后 PASS / FAIL。只写这一个文件。
