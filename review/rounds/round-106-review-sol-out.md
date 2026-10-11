# Round 106 Codex 定向复审

范围：`a365537`（`git log -1 --format=%h -- ky/storage/route_store.py`）。运行只使用该提交的系统临时目录归档；未跑全量测试。

| 项目 | 意见 | 证据与判断 |
| --- | --- | --- |
| A1：发布与记录身份之间的窗口 | 不改 | `ky/storage/route_store.py:309-321` 在 `os.link` 前对自身临时文件 `os.stat`，硬链接发布后沿用该 inode 身份。第 105 轮原探针（真正链接后立即删目标、写同名外部文件，再令 manifest 的 `replace_bytes` 抛错）由 `tests/contract/test_route_plan_port.py:268-288` 精确覆盖：单跑通过，外部字节保留；在临时归档中退回“链接后 stat 目标”，同一测试失败，提示 `rollback deleted the swapped-in file`。正常 manifest 失败后的回滚及重试测试单跑通过。原窗口已关闭。 |
| 规格中的剩余窗口 | 建议改 | `contracts/route_plan.md:40-41` 所述“身份核对与删除之间仍有极短窗口”与 `ky/storage/route_store.py:276-285` 相符；因此不宣称无锁并发安全是准确的。但规格第 39 行称“硬链接发布后立即记录目标的 `st_dev` / `st_ino`”，现实现是发布前记录**临时文件**的身份（第 312、314 行），应同步改为该时序，免得后续实现按过时描述回退。此文案偏差不影响本次 A1 修复。 |
| B2：无 `KY_WORKSPACE` 的向上发现补测 | 不改 | `tests/contract/test_planner_port.py:635-679` 分别覆盖环境变量指定和 cwd 向上发现无效注册表，并对两种 `submit --plan` 断言退出码 2、目标 store 不存在；单跑通过。在临时归档中只把 `_workspace_for_plan_rejection` 的发现步骤退回“无显式参数与环境变量时直接返回 None”，同一测试于 `upward search` 子用例失败（day submit 实得退出码 0）。补测能锁住所针对的回退。 |

**结论：PASS。** 建议随后修正规格第 39 行的身份记录时序；本轮没有阻断项。
