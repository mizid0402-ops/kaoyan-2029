# 定向复审：第 96 轮"必须改"（聚合工具换行）与两条建议

遵守 `AGENTS.md`（不跑全量）。范围只限本轮修复提交 `a84d9cf`（`git show a84d9cf`；运行用 `git archive a84d9cf`，照前几轮补原始资料与 `products` 空目录）。

决策者处理：
1. **必须改（换行）**：`tools/aggregate_topic_weights.py` 在调用点把 `"\n"` 换成 `os.linesep` 再交给 `replace_bytes`，恢复 `8f31a05` 前 `write_text` 的文本模式换行；
   行尾归一留给 WP-G（C3，连同记录它们的哈希一起改）。新测试 `test_write_bytes_match_fixed_baseline` 把 `8f31a05` 的工具与当前工具放在同一份临时输入上 `--write`，按原始字节比较；
   基线固定到提交哈希并断言取到的是含 `_replace_file` 的旧版。决策者已撤修复验证该测试变红、还原后哈希一致。
2. **建议（I1 测试）**：`test_planner_port` 改为断言输入包 `review_clip` 等于 `ky preflight --json` 删去 `config` 后的**整个值**；把 `subject_allocation` 改成 `[]` 的诱变已变红。
3. **建议（H1 规格）**：`contracts/planner_port.md` 信任边界补一句——可信编排者不得把 `staging/` 下的文件交给 `--plan`，端口不检测这种路由。
   你建议的"对该路径 fail-closed 拒绝"暂不做：`--plan` 可配显式 `--store` 而不加载注册表，拒绝需要先定"没有注册表时怎么判 staging"，放到 E3b 与路线提交一起定。可以反驳。

请判断：换行修复与字节对照是否充分（含非 Windows 平台下两版是否仍逐字节一致）；两条建议的处理是否可接受。

产物：`review/rounds/round-98-review-sol-out.md`，每项"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
