# Round 89 Codex 复审：`cd8918d`

范围：只看 `git show cd8918d` 的扫描范围修复与 `--date` 回归测试。用 `git archive cd8918d` 解至系统临时目录；探针及撤修复变异均在该临时归档中。未跑全量测试，未使用主工作区正在修改的代码。下列行号均指该提交。

| 项目 | 意见 | 可复现输入与证据 |
|---|---|---|
| 根目录及多层目录错位事件 | **不改** | `ky/storage/day_plan_store.py:625-632` 改用 `root.rglob("completion--*.yaml")`，仍将解析所得 `event.day` 对照存储标准路径。把 `write_completion_event(day=2026-09-10, delivered_words=[alpha])` 的合法文件分别单独移至 `state/completion--2026-09-10.yaml`、`state/2026-09/day_plans/completion--2026-09-10.yaml`，两处实测均抛 `StorageError`；错日期文件名及 `state/misc/` 中的事件也均被拒绝。第 87 轮遗漏已关闭。 |
| 存储自身文件及临时残留 | **不改** | 标准事件与同月 `day_plans_manifest.yaml`、`month_close.yaml`、版本日计划文件、`.completion--2026-09-10.yaml.deadbeef.tmp` 并存时，`delivered_words()` 实测仍只返回 `{'alpha'}`。`ky/storage/day_plan_store.py:466-473` 的其他文件名不匹配扫描模式；原子写入真实临时名为 `.{final_path.name}.{uuid}.tmp` (`:135-141`)，同样不匹配。没有发现递归扫描误伤。 |
| `--date` 拒绝测试 | **不改** | `tests/test_eng1_vocabulary.py:60-67` 调新工具传 `--date 2026-09-25`，断言退出码 2 且 stderr 提及 `--date`；在归档中单跑 1/1 通过。临时给解析器恢复一个无作用的 `--date` 参数后，此测试变红（1 个失败），能抓到该回退。 |
| M1 回归断言 | **不改** | `tests/test_day_plan_store.py:231-247` 新增根目录及多层目录两个输入；定向模块 19/19 通过。临时把 `rglob` 改回旧 `glob("*/completion--*.yaml")` 后，该测试变红（2 个子用例失败），断言足以锁住本轮修复。 |

**整体：PASS。** 本轮指定的错位事件与误伤边界均已验证；未发现新的阻断项。
