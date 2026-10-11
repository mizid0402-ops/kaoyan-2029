# 任务书：修 sol 第 102 轮 A1 / A2 / B2 / B4 与建议 B5 / B6（M13 / M19 / M14）

先读仓库根 `AGENTS.md`，再读 `review/rounds/round-102-review-sol-out.md`（全文，复现输入都在里面）、`contracts/route_plan.md`、`contracts/planner_port.md`、
`ky/storage/route_store.py`、`ky/planner/port.py`、`ky/__main__.py` 的 `_workspace_for_plan_rejection`、`ky/workspace.py` 的 `find_workspace` / `load_workspace`。

你在主仓库 `F:\workspace\kaoyan-ai-system` 工作，只改上面列出的实现与规格，以及 `tests/contract/test_route_plan_port.py`、`tests/contract/test_planner_port.py`。

## 要修的（决策者已定做法；有更好的写法先在报告里提）

1. **A1 回滚只删自己发布的文件**：`os.link` 发布后立刻记下目标的身份（`os.stat` 的 `st_dev` / `st_ino`）；manifest 替换失败回滚时，先 `os.stat` 目标，身份一致才删除，不一致（或已不存在）就不删，原异常照抛。
   规格写明：身份核对与删除之间仍有极短窗口，只防"不遵守锁的写者在回滚前替换了文件"这一情形。测试：patch `replace_bytes` 在抛错前把目标换成外部文件 → 外部文件保留；撤掉核对后该测试变红。

2. **A2 写入前校验来源**：`write_route_plan` 在写任何文件前，用与 manifest 解析**同一个**校验函数检查 `actor`（字符串）与 `input_hash`（`None` 或小写 64 位十六进制），不合格报 `StorageError`（路径 `input_hash` / `actor`），不留任何文件。
   测试：`input_hash="x"` 与 64 位大写各被拒，目录字节不变。

3. **B2 已发现但无效的注册表 fail-closed**：`_workspace_for_plan_rejection` 改为：先 `find_workspace(explicit=workspace_arg)`；**只有**它报"找不到"且没给 `--workspace` 时返回 `None`；找到后 `load_workspace(找到的路径)` 的任何错误都照抛（CLI 退出 2）。
   注意 `KY_WORKSPACE` 环境变量也属于"找到"。测试：临时目录放一份无效注册表（例如只有 `schema_version: 2` 与 `subjects: {}`），两种 `submit --plan` 指向其 `staging/` 下文件都退出 2 且不写。

4. **B4 staging 子目录越界**：写包（日、路线两种）与查包（日、路线两种）都要同时确认 ① `(staging/<子目录>).resolve()` 在 `staging.resolve()` 之内，② 目标或候选的真实路径在 ①之内。
   把这两步抽成一个有名字的辅助函数，写包、查包、`_validate_staging_path` 共用，不要四处各写一份。测试：`staging/inputs` 建成指向 staging 外目录的 junction（`_winapi.CreateJunction`；建不了就 `skipTest`），创建路线输入包与 apply 路线提案都被拒；**测试结束前 `os.rmdir` 拆掉 junction**。

5. **B5（建议，采纳）**：按 `route--*--<hash[:12]>.json` 找到的候选中，规范化哈希不等于提案 `input_hash` 的（含读不出 JSON 的）一律跳过；哈希匹配的候选里 `kind` 不对报错；匹配的有效包多于一个报歧义；一个都没有报"不存在"。规格与实现按此一致。测试：合法包旁放一个 `{}` 的同前缀诱饵，apply 成功。

6. **B6（建议，采纳）**：补一条测试：基于 r1 生成日输入包并写好日提案，提交路线 r2 后，apply 该日提案被拒为"输入已变化"。

## 不做的

- 不改路线格式、比较并交换、锁语义；不改日计划护栏；不做 E4。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_route_plan_port tests.contract.test_planner_port tests.test_cli
```

## 报告

`review/rounds/round-104-sol102-fixes-luna.md`：每项的落点、撤修复验证、验收输出、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
