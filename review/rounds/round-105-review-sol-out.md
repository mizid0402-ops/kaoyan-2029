# Round 105 Codex 定向复审：`79623ee`

只审 `git show 79623ee` 对第 102 轮 A1/A2/B2/B4 及 B5/B6 的修复。运行对象是 `git archive 79623ee` 的系统临时副本，已补入被忽略的原始资料和注册表要求的 `products` 空目录；固定旧版测试设 `GIT_DIR`。未跑全量，未改实现。

| 项 | 意见 | 本机复现与判断 |
| --- | --- | --- |
| **A1：回滚身份保护** | **必须改** | 第 102 轮原输入（`replace_bytes` 抛错前删除 r1 并写入同名 `b"external replacement"`）现保留外部文件；`os.stat(final_path)` 报错时也不删除 r1，最终仍抛原 `OSError("manifest unavailable")`。在本机临时目录重复 100 次，硬链接两路径的 `(st_dev, st_ino)` 100 次相同，新建同名替换文件 100 次均不同且 inode 非零，说明本机 Windows 文件系统上这组值能识别**已记录身份之后**的替换；其他卷类型未核实。**仍有可复现的较早窗口**：patch `os.link`，先真正 `link(temp, final)`，随即删除 `final` 并写入同名外部文件，再返回；令随后 `replace_bytes` 抛错。`ky/storage/route_store.py:317` 此时对已替换的 `final` 取身份，`:273-286` 回滚比较成功并删掉外部文件；探针结果 `external_before_identity_survived=False`。`contracts/route_plan.md` 只声明“身份核对与删除之间”的剩余窗口，没有覆盖“发布与首次记录身份之间”的窗口。建议在发布前从临时文件取得本次 inode 身份，再执行 `os.link`；保留已明示的核对至删除窗口。新增测试只在 `replace_bytes` 阶段替换目标，撤去身份比较会变红，但抓不到这个早期窗口。 |
| **A2：来源校验与无写入** | **不改** | `ky/storage/route_store.py:77-92` 的 manifest 条目解析与 `write_route_plan` 第 211 行共用 `_validate_provenance`。原输入 `input_hash="x"`、`"A"*64` 均在创建根目录前报 `StorageError(path="input_hash")`；`actor=None` 报 `path="actor"`。在已有 r1 的库上提交非法来源 r2，比较前后全部文件字节相同且无锁残留。临时撤掉写入口校验，新增 `test_invalid_provenance_is_rejected_before_any_file_is_written` 变红。 |
| **B2：发现到损坏注册表** | **不改；建议补测试** | `ky/__main__.py:114-124` 先 `find_workspace`，只在无显式参数、无 `KY_WORKSPACE` 且**找不到文件**时跳过；找到的文件再由 `load_workspace` 校验，错误不被吞。把 `kaoyan.workspace.yaml` 写成 `schema_version: 2\nsubjects: {}\n`，分别在向上发现和设置 `KY_WORKSPACE` 下，用有效裸日计划/路线文件及显式 `--store` 运行两种 `submit --plan`：四次均退出 **2**，目标库未创建。`test_plan_cli_fails_closed_for_discovered_invalid_registry` 目前只设 `KY_WORKSPACE`：临时只撤 `find_workspace` 这一步、保留环境变量防护，该测试仍**通过**；连环境变量防护一起退回旧实现才变红。建议再加一条不设 `KY_WORKSPACE` 的向上发现坏注册表断言，精确锁住本轮 B2 的另一半。 |
| **B4：包与提案的真实路径边界** | **不改** | `ky/planner/port.py:139,156,162-177,220-237,324-330`：日/路线输入包写入、日/路线包查找，以及 `day_plans`/`routes` 提案路径都调用 `_resolve_staging_path`。辅助函数先校验解析后的 category 在 staging 内，再校验解析后的目标在 category 内。把 `staging/inputs` 建为指向外部目录的 Windows junction：日/路线包创建及两种 staged apply 全部抛 `ContractError`，外部目录无新增文件；把 `staging/day_plans`、`staging/routes` 各设为指向外部的 junction，两种提案也均被拒。决策者删去仅转发的辅助函数与旧重复检查后，上述路径仍覆盖。临时撤掉 `category_root.relative_to(staging)`，新增 junction 测试变红。 |
| **B5：同前缀诱饵与唯一性** | **不改** | `ky/planner/port.py:324-349` 先验证候选真实路径，再按规范化 JSON 哈希筛选。合法包旁放同 `hash12` 文件、内容 `{}`，原提案现成功应用；换成无效 JSON `{bad` 也被跳过；另放一份与合法包**同字节**但不同文件名的候选则报 ambiguous。三种结果与修订的 `contracts/planner_port.md` 一致。临时撤哈希不符候选的 `continue`，新增诱饵测试变红。 |
| **B6：路线换版使旧日提案过期** | **不改** | 新增 `test_day_proposal_expires_after_route_revision_changes` 先应用 r1，再生成日包和日提案，应用 r2 后旧日提案报“输入已变化”。`ky/planner/port.py:40-80` 的日包包含覆盖当天的路线 revision；临时让 `_route_plan_for_day` 恒返 `None`，该测试变红。范围外仍为 null 的既有规则不变。 |

定向测试：`py -3.12 -m unittest tests.contract.test_route_plan_port` **14/14**、`tests.contract.test_planner_port` **28/28**、`tests.test_cli` **41/41**。所有探针、撤修复与 Windows junction 均在临时归档中运行。B2 测试的单点撤修复保持绿色，以及 A1 新测试漏掉的发布至记录身份窗口，已分别标明。

**结论：FAIL。** A2/B2/B4/B5/B6 的行为已满足本轮要求；A1 仍可删除在身份记录前替换进来的外部文件。下轮只需把本次发布物的身份在 `os.link` 前确定，并用上述早期替换输入加定向回归测试。
