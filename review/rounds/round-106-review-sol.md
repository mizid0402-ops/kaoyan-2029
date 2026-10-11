# 定向复审：sol 第 105 轮 A1（发布与记录身份之间的窗口）

遵守 `AGENTS.md`（不跑全量）。范围只限本轮修复提交（见本文件所在提交；`git log -1 --format=%h -- ky/storage/route_store.py`），运行用 `git archive <该提交>`。

决策者处理：`_write_version` 在 `os.link` **之前**对自己的临时文件 `os.stat` 取 `(st_dev, st_ino)`（硬链接共用同一 inode），不再发布后 stat 目标。
新测试 `test_rollback_keeps_file_swapped_in_right_after_publish` 用你第 105 轮的输入（patch `os.link`：真正链接后立刻删目标并写入同名外部文件，再让 `replace_bytes` 抛错），断言外部文件保留；撤修复后该测试失败（"rollback deleted the swapped-in file"）。
另采纳 B2 建议：`test_plan_cli_fails_closed_for_discovered_invalid_registry` 增加不设 `KY_WORKSPACE` 的向上发现子用例；只撤 `find_workspace` 一步时该子用例变红。

请用你第 105 轮的原探针重跑，判断 A1 是否关闭、规格对剩余窗口（核对至删除）的表述是否仍准确，以及 B2 补测是否锁住。

产物：`review/rounds/round-106-review-sol-out.md`，每项"必须改 / 建议改 / 不改"，最后 PASS / FAIL。只写这一个文件。
