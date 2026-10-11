# 第 249 轮任务书：WP-IO2 定点复审（gpt-6.1-sol，续 sol61-m18）

luna-c 已在主工作区按你第 246 轮报告返工（说明：`review/rounds/round-237-m29-io2-luna.md` 末节"第 248 轮返工"；任务书 `review/rounds/round-248-m29-io2-fix-task.md`）。
决策者另把 `ky/timetable_io/ics_import.py` 的 `_instance_rows`（67 行）拆出 `_period_mismatches`、`_event_summary` 两个辅助函数，行为不变。
主仓库仍处在 `wip/io2` 的未提交合并中；用 `git diff --cached` 与 `git diff` 看改动。

请复审：R1（导入只加载一次学校档案，预览复用已加载对象）、R2（剔除后再查时区；`EXDATE` 每个值；未知 `TZID` 违约）、R3（节次失配全部汇总后违约、不发布）是否关闭；
建议项（新增测试、`*` 标记、清理、混用时间域的契约错误）是否正确；有无新问题；能否合并。只跑相关单个模块或单项，不跑全量。

输出 `review/rounds/round-249-m29-io2-rereview-sol61.md`，格式同前。不联网；只写这一份报告；不修改其他文件；不读仓库外文件；不写个人数据。
