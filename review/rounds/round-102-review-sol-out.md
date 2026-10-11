# Round 102 Codex 复审与独立评审

范围：A 仅复审 `git show 0d106be` 对第 99 轮 F2/S2/S3/S4 的修复及其直接回归；B 审 `git diff a256d36^1 a256d36` 与 `review/rounds/round-100-wp-e3b-task.md`、两份端口规格。全部运行在 `git archive a256d36` 的系统临时副本，补入被忽略的原始资料和注册表要求的 `products` 空目录；固定旧版对照设 `GIT_DIR` 指向仓库。未跑全量，未改实现。

## A. `0d106be`：第 99 轮修复

| 项 | 意见 | 原复现、直接回归与证据 |
| --- | --- | --- |
| F2 超大整数权重 | **不改** | 将合法路线 `months[0].subject_weights.subject` 改为 `10**1000` 并写成 YAML，`ky route submit --plan <该文件> --store <临时库>` 现退出 **2**、无 traceback 且未创建库；`parse_route_plan` 抛 `RoutePlanError`，路径为 `route_plan.months[0].subject_weights.subject`。`ky/schedule/planning.py:301-310` 捕获 `math.isfinite` 的 `OverflowError`；临时撤去转换后新增单条测试变红。 |
| S2 原 manifest 篡改输入 | **不改** | 用第 99 轮的字符串 revision、非映射条目、`schema_version: true`、`../outside.yaml`（根外文件与 r1 同字节），再加断号，均由 `ky/storage/route_store.py:41-111,129-143` 抛 `StorageError`，路径分别落在相应字段；字符串 revision 的 CLI 提交现退出 **2**、无 traceback。`_load_entry` 还核对路线内部的 revision/route_id（:162-177）。精确键、类型、连续顺序、固定文件名及摘要格式未发现可由上述 YAML 结构绕过的输入。临时把 `_read_manifest` 改回直接返回原始映射，新测试变红。 |
| S3 manifest 替换抛错 | **不改，另见 A1** | 临时让 `replace_bytes` 抛 `OSError("manifest unavailable")`：`ky/storage/route_store.py:267-271` 删除刚发布的 r1，目录无版本/manifest 文件；重试 r1 成功。新增回滚测试在撤掉 `unlink` 后变红。崩溃留下孤儿版本的手动删除流程写在 `contracts/route_plan.md:49-53`；已有文件在 :247-248 被拒，不会被本次发布覆盖。 |
| S4 检查后发布的覆盖竞态 | **不改** | 在 `os.link(temp, route--r1.yaml)` 调用前插入外部文件，Windows 归档实测 `FileExistsError` 转为 `StorageError`，外部字节 `b"external writer"` 不变；`ky/storage/route_store.py:282-303` 不回落 `os.replace`，临时文件由 `finally` 清理。改回 `os.replace` 后新测试变红。硬链接不支持时显式拒绝符合修订规格。 |
| A1 回滚可能删除别人替换后的文件 | **必须改** | `ky/storage/route_store.py:267-271` 无条件 `final_path.unlink()`，并未确认目录项仍指向本次 `os.link` 发布的 inode。定向探针：patch `replace_bytes`，在它抛 `OSError` 前先 `route--r1.yaml.unlink()`、再以同名写入 `b"external replacement"`；`write_route_plan` 报错后该外部文件也被删除。此竞态需要不遵守 `.routes.lock` 的写者，但 S4 的原子不覆盖正是为此类写者设防。至少在回滚前保留并核对本次发布对象的身份，失去所有权时不得删除目标；相应定向测试应在撤掉核对后变红。 |
| A2 公开写接口能生成自己拒读的 manifest | **必须改** | `write_route_plan(make_route(), actor="human", input_hash="x")` 返回成功并写入 r1；紧接 `store.current()` 在 `routes_manifest.yaml.revisions[0].input_hash` 抛 `StorageError`。同样复现于 64 位大写摘要。`_parse_manifest_entry`（:82-86）要求 null 或小写 64 位十六进制，但 `_write_locked`（:253-268）直接序列化调用方参数。`input_hash` 是公开写接口的 `str | None` 参数，须在发布版本前用同一规则校验，或先验证将写出的 manifest；失败不留版本文件。新增测试尚未覆盖该路径。 |

**A：FAIL。** F2/S2/S3/S4 的第 99 轮原输入均已关闭；A1 是修复引入的删除竞态，A2 会从公开端口写出无法读取的状态。`route_plan_port` 单模块 **12/12 通过**，但未覆盖 A1/A2。

## B. `a256d36`：WP-E3b

| 项 | 意见 | 可复现输入、结果与规格对照 |
| --- | --- | --- |
| B1 路线 staging、提案头与同一 apply | **不改** | `ky/planner/port.py:180-230,317-331,359-394` 对路线提案校验精确头字段、actor、必填小写摘要、`stage1_input_hash == input_hash`、真实路径在 `staging/routes`、包及新鲜度，然后调用 `_apply_route_plan`；人写路线也调用同一个函数。`tests/contract/test_planner_port.py:241-343` 覆盖成功、缺摘要、哈希不等、错 kind、过期、错误版本和共同 apply。临时撤 `stage1_input_hash` 约束或 kind 检查，相关单条测试均变红。 |
| B2 损坏但已发现的注册表使 `--plan` 防护 fail-open | **必须改** | `ky/__main__.py:113-120` 的 `_workspace_for_plan_rejection` 在**没有显式 `--workspace`**时吞掉任意 `ContractError`，把“找到但加载失败”也当作“没发现注册表”。临时工作区放 `kaoyan.workspace.yaml` 内容 `schema_version: 2\nsubjects: {}\n`，把合法裸路线放在 `staging/routes/bare.yaml`，从该工作区执行 `ky route submit --plan staging/routes/bare.yaml --store <临时库>`：退出 **0**，按 `human/null` 写入。相同方法对 `day-plan submit --plan staging/day_plans/bare-day.yaml --config <有效配置> --store <临时库>` 也退出 **0**。`contracts/planner_port.md` 只允许“无显式且发现不到注册表”跳过；这里注册表**已发现却无效**，应退出 2。区分“未找到”与“找到后校验失败”，后者 fail-closed。 |
| B3 正常 `--plan` 路径别名与无注册表规则 | **不改（受 B2 限制）** | 在有效注册表下，对同一 staging 路线文件分别传原路径、大小写变体、指向 `staging/routes` 的 junction 别名，`reject_staging_plan_path`（`ky/planner/port.py:304-314`）在 Windows 都拒绝。`tests/contract/test_planner_port.py:514-570` 的无注册表、显式 `--store` 用例通过，符合已定跳过规则；显式无效 `--workspace` 会重新抛错。`route submit --plan <不存在文件> --workspace <不存在注册表>` 现退出 **3**，第 99 轮 C2 已关闭（`ky/__main__.py:646-649`）。 |
| B4 `staging/inputs` junction 越界 | **必须改** | `ky/planner/port.py:169-177` 只比较目标父目录与已解析的 `staging/inputs`，没有确认 `inputs` 本身仍在已解析的 staging 下；`:334-351` 查包也只有“候选在已解析 inputs 下”一层。临时工作区把 `staging/inputs` 建成指向同工作区另一个 `outside-inputs` 目录的 Windows junction，执行 `create_route_planner_input`：返回成功，真实 JSON **写在 outside-inputs**；随后把合法提案放在 `staging/routes/`，`apply_staged_route_proposal` 成功写入 r1，接受了根外输入包。规格要求包在 `write_target("staging")/inputs/` 且越界拒绝。写包和查包两处都应检查 `inputs.resolve()` 位于 `staging.resolve()` 内，接着检查目标真实路径；回归测试需覆盖 junction。 |
| B5 路线包确定性、唯一性和过期 | **建议改** | `ky/planner/port.py:90-107,152-166,253-261,334-394` 以同一 canonical JSON 字节算 SHA、写 `route--<day>--<hash12>.json`，查到的包重算规范化哈希并验 `kind`，按包中 day 重建当前包。现有相同输入两次字节/摘要相同；队列改变后旧路线提案被拒。一个较严格的偏差：在合法包旁另放 `route--0000-01-01--<hash12>.json`，内容 `{}`，合法包和提案未动，apply 却在扫描诱饵时立即报 hash mismatch；`contracts/planner_port.md` 写的是“恰好一个**哈希匹配**的包”。建议定义非匹配候选是跳过还是 fail-closed，并使规格与实现一致；同哈希的两个有效文件仍应报歧义。 |
| B6 日输入包及旧提案过期 | **不改；建议补定向断言** | `ky/planner/port.py:40-80` 对 `[month.start, month.end_exclusive)` 取 `route_plan_to_mapping` 中该月映射，范围外/null 路线保持 `null`。归档探针于路线起日和下月边界分别得到 index 0/1；写入 r1 后同日输入包摘要变化，先前日提案被拒为过期。无路线时 `tests/contract/test_planner_port.py:206-224` 固定 `f0df351d80e3cd0b042ecc88fa11ccc116b65c98` 旧源码，断言其仍含 `"route_plan": None` 且无新路线输入函数，在相同临时配置上按 canonical **原始字节**比对，基线可信；临时改新包为 `route_plan: []`，该测试变红。现有测试尚未直接断言“路线换版使旧日提案过期”，建议补一条。范围外的日包仍为 null，换路线版本不会仅凭该字段使它过期，这是规格中 null 规则的自然边界。 |
| B7 日计划与新增测试强度 | **不改（B2/B4 为缺口）** | `tests.contract.test_planner_port` **24/24**、`tests.contract.test_route_plan_port` **12/12**、`tests.test_cli` **41/41**、`tests.test_day_plan_store` **19/19**；未跑全量。临时撤路线 stage1 哈希校验、路线包 kind 检查、日包新增字段、`--plan` staging 拒绝，各自对应单条测试都变红。现有断言无法检出 B2 的“已发现但损坏”与 B4 的 junction 越界；新增测试应分别证明两种 submit 均拒绝前者，以及输入包创建/查找均拒绝后者。 |

**B：FAIL。** B2 使已发现的坏注册表绕过 `--plan` staging 防护，B4 让包写入与读取越过 staging 根；两项都有本机实际复现。
