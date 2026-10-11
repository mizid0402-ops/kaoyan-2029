# 任务书：修 sol 第 99 轮对 WP-E3a 的四个"必须改"（M11 / M13）

先读仓库根 `AGENTS.md`，再读 `review/rounds/round-99-review-sol-out.md`（全文，复现输入都在里面）、`contracts/route_plan.md`、
`ky/schedule/planning.py`（`parse_route_plan` 及其辅助函数）、`ky/storage/route_store.py`、`ky/storage/atomic.py`、`tests/contract/test_route_plan_port.py`。

你在主仓库 `F:\workspace\kaoyan-ai-system` 工作。**只改**：`ky/schedule/planning.py`、`ky/storage/route_store.py`、`contracts/route_plan.md`、
`tests/contract/test_route_plan_port.py`。另一个实现者正在别的 worktree 改 `ky/__main__.py` 与 `ky/planner/`，**不要碰这两处**（sol 的 C2 由决策者稍后处理）。

## 要修的（决策者已定做法；有更好的写法先在报告里提）

1. **F2 超大整数权重**：`subject_weights` 的值若无法转成有限浮点数（含 `OverflowError`），报 `RoutePlanError`，路径 `...subject_weights.<科目>`。

2. **S2 manifest 读取 fail-closed**：把 manifest 解析抽成一个有名字的函数（例如 `_parse_manifest`），一次校验全部：
   - 顶层键恰好 `schema_version`、`route_id`、`revisions`；`schema_version` 为精确整数 1（拒绝 `true`）；`route_id` 非空字符串；`revisions` 为列表。
   - 每项键恰好 `revision`、`path`、`sha256`、`actor`、`input_hash`；`revision` 为精确整数且整列表从 1 起连续递增（唯一、有序）；
     `path` **必须等于** `route--r<revision>.yaml`（不是任意相对路径，杜绝越出存储根）；`sha256` 为小写 64 位十六进制；`actor` 为字符串；`input_hash` 为 `null` 或小写 64 位十六进制。
   - 读出版本后，路线自身的 `revision` 与 `route_id` 必须等于该条目与 manifest 的值，否则报错（防止来源与路线错配）。
   - 任何不符报 `StorageError`，路径指到具体字段（如 `routes_manifest.yaml.revisions[0].path`）。写入路径同样经这个函数读取当前 manifest。

3. **S3 manifest 写失败回滚**：版本文件已发布、manifest 替换失败时，删除本次新发布的版本文件后再抛出（锁内、本次创建，删除是安全的）。
   崩溃窗口（进程在两步之间死亡）会留下未登记的 `route--r<N>.yaml`：此时再提交同一版本应报 `StorageError`，消息指明"未登记的版本文件，确认后手动删除"与文件路径；规格写明这条恢复办法。

4. **S4 不覆盖的发布**：临时文件校验通过后，用 `os.link(临时文件, 目标)` 发布（目标已存在时原子失败，Windows / POSIX 都不覆盖），再删临时文件；
   `FileExistsError` 报 `StorageError`（同 S3 的未登记提示）。硬链接不可用的文件系统报 `StorageError` 说明原因，**不要**静默回落到 `os.replace`。去掉发布前那次 `exists()` 判断改由 `os.link` 保证（或保留仅为更早给出清晰错误，但不能作为唯一保证）。
   规格把"版本文件不可覆盖"写成由原子不覆盖发布保证。

## 测试（只写这些，加在 `tests/contract/test_route_plan_port.py`）

每条都要在撤回对应修复时变红（在报告里写你怎么验证的）：
- F2：`10**1000` 权重被拒，路径正确。
- S2：`schema_version: true`、`revision: "1"`、`revisions: ["x"]`、`path: ../outside.yaml`（根外放同字节文件）、版本不连续、路线文件 `route_id` 与 manifest 不符——各被拒为 `StorageError`（可用 subTest）。
- S3：patch `ky.storage.route_store.replace_bytes` 抛 `OSError` 提交 r1 → 目录里没有 `route--r1.yaml`，之后正常提交 r1 成功；手工放一个未登记的 `route--r1.yaml` 再提交 r1 → 报"未登记"错误。
- S4：在发布前让目标路径出现（patch 发布前的某一步去创建它）→ 提交失败且外部字节不变。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_route_plan_port tests.test_planning
```

## 报告

`review/rounds/round-101-e3a-sol99-fixes-luna.md`：每项的落点、撤修复验证、验收输出、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
