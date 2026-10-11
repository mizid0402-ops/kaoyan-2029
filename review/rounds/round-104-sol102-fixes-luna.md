# Round 104：sol 第 102 轮 A1 / A2 / B2 / B4 / B5 / B6 修复报告

## 落点与验证

- **A1 回滚身份保护**：`ky/storage/route_store.py` 在硬链接发布后立即用 `os.stat` 记录
  `st_dev` / `st_ino`。manifest 替换失败时，只有目标身份仍匹配才删除；目标不存在、身份变化或
  stat/unlink 报错时保留目标，并继续抛出原替换异常。`contracts/route_plan.md` 记录了身份核对与
  删除间仍有极短窗口，以及本检查只覆盖不遵守锁的写者替换文件这一情形。
  定向撤修复验证：临时移除身份比较后运行
  `py -3.12 -m unittest tests.contract.test_route_plan_port.TestRoutePlanStore.test_manifest_failure_preserves_replaced_external_version_file`，
  测试失败，外部文件已被删；恢复身份核对后通过。
- **A2 写入前校验来源**：`ky/storage/route_store.py` 将 manifest 读取和写入前校验共用
  `_validate_provenance`。非法 `input_hash` 报 `StorageError(path="input_hash")`，校验先于根目录、锁及
  版本文件写入。新增测试分别拒绝 `x` 与 64 位大写摘要，并断言目录字节不变。
- **B2 注册表 fail-closed**：`ky/__main__.py` 先调用 `find_workspace(explicit=...)`，只有未显式指定且
  没有发现注册表时跳过护栏；发现后所有 `load_workspace` 错误均保留。`KY_WORKSPACE` 发现路径也适用。
  新测试用无效 schema 注册表和 `KY_WORKSPACE`，分别验证日计划、路线 `submit --plan` 均退出 2，存储目录
  均未创建。
- **B4 staging 子目录边界**：`ky/planner/port.py` 新增 `_resolve_staging_path`，统一确认解析后的
  `staging/<category>` 位于 staging 内，且目标真实路径位于该子目录内。日/路线包写入、日/路线包查找及
  `_validate_staging_path` 共用此检查。junction 测试验证路线包写入与路线提案 apply 均拒绝 staging 外
  的 `inputs` 目录；测试结束用 `os.rmdir` 拆除 junction。当前 Windows 环境中该测试实际运行并通过，未跳过。
- **B5 候选包确定性**：`ky/planner/port.py` 对路线输入候选重算规范化哈希；哈希不符、不可读或无效 JSON
  的候选跳过。哈希匹配后再验证 mapping 与 kind，匹配有效包多于一个报歧义，无匹配包报不存在。
  `contracts/planner_port.md` 已同步。新增合法包旁放 `{}` 同名前缀诱饵的 apply 成功测试。
- **B6 日提案过期**：新增定向测试：先按当前输入提交路线 r1，再生成日包和日提案，提交路线 r2，最后断言
  apply 旧日提案报“输入已变化”。既有 `contracts/planner_port.md` 已说明路线修订会改变覆盖范围内的日包，
  因此无需新增不同语义的规格条款。

## 验收

运行任务书指定命令：

```text
py -3.12 -m unittest tests.contract.test_route_plan_port tests.contract.test_planner_port tests.test_cli
Ran 83 tests in 19.585s
OK
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 建议

- 暂无新增建议。A1 身份核对与 unlink 之间仍有极短竞态窗口，规格已明确该限制；本轮不扩展锁或发布协议。
