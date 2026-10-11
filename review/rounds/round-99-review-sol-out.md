# Round 99 Codex 独立评审：WP-E3a

范围固定为 `git diff 36024f9^1 36024f9`；运行对象是 `git archive 36024f9` 解出的系统临时目录，已补入被忽略的 `data/raw_materials/` 和注册表要求的 `products` 空目录。以下探针均未触碰仓库数据。结论：**FAIL**；格式与正常版本提交基本符合规格，但损坏 manifest、提交中途失败和版本文件竞态会破坏存储承诺。

## 1. 格式与解析

| 项 | 判断 | 证据、可复现输入与处理建议 |
| --- | --- | --- |
| F1：映射互逆、键、类型、日期、闭合性 | 不改 | `ky/schedule/planning.py:240-289,292-375` 检查两层精确键、整数排除布尔值、日期排除 `datetime`、权重有限性，最后调用 `validate_route_plan`。归档内 `tests.contract.test_route_plan_port` 的合法路线和未加引号 YAML 日期往返成功；未知键、缺键、布尔 revision、日期时间、字符串 schema 和容量不闭合均按测试断言的路径拒绝。`load_yaml_text` 是 YAML 入口，重复键仍由该端口拒绝。针对普通 YAML 输入未发现绕过 `validate_route_plan` 的路径；直接构造失范 `RoutePlan` 并调用序列化器不属于解析器承诺。闭合性错误保留原有 `months[i]...` 路径，符合任务书“不改现有语义”。 |
| F2：超大整数权重未转成契约错误 | **必须改** | `ky/schedule/planning.py:301-305` 对任意 Python 整数调用 `math.isfinite(value)`。把合法路线映射 `months[0].subject_weights.subject` 改为 `10**1000`，经 `yaml.safe_dump` 写入临时 `plan.yaml`，运行 `py -3.12 -m ky route submit --plan <文件> --store <临时目录>`：退出 **1** 且 traceback 为 `OverflowError: int too large to convert to float`；`ky/__main__.py:672-676` 不捕获它。应将这个值拒绝为带 `months[0].subject_weights.subject` 路径的 `RoutePlanError`，CLI 退出 2。非有限浮点数已有检查；此项是超大**有限整数**边界。 |

## 2. 版本存储与锁

| 项 | 判断 | 证据、可复现输入与处理建议 |
| --- | --- | --- |
| S1：正常比较并交换与来源记录 | 不改 | `ky/storage/route_store.py:123-181` 在独占锁内比较当前最后一项、revision 与 route_id，再写版本和 manifest。r1→r2、跳号、旧号、换 route_id、旧版原始字节、逐版 actor/input_hash、版本 SHA 篡改均由 `tests/contract/test_route_plan_port.py:108-155` 检验。锁文件路径错误和崩溃残留后人工确认并删除写在 `contracts/route_plan.md:17-20`；归档探针预置 `.routes.lock` 后 `submit` 退出 2、错误指向锁路径。残留锁降低可用性，但这是明示且可手动恢复的取舍，可接受。 |
| S2：manifest 结构与路径没有 fail-closed | **必须改** | `ky/storage/route_store.py:48-83,93-109,144-147` 只检查顶层大致形状。写入合法 r1 后把 `routes_manifest.yaml` 的 `revisions[0].revision` 改成字符串 `"1"`，再提交合法 r2：`latest.get("revision", 0) + 1` 抛 `TypeError`，CLI 退出 **1** 并显示 traceback。把 `revisions` 改为 `["x"]` 后 `route show --json` 也退出 1。把该项 `path` 改为 `../outside.yaml`，在根目录外放置同字节 r1 文件，`current()` **成功读到根外文件**。另将 `schema_version` 改为 YAML `true`，`current()` 将其当作版本 1 接受。必须在读取 manifest 时检验精确类型、条目字段、revision 从 1 连续有序且唯一、条目与所指路线的 route_id/revision 相符，并把 path 限定为本库相应版本文件，越界或结构异常报 `StorageError`。否则历史来源也能与路线错配。 |
| S3：manifest 写失败留下未登记版本 | **必须改** | `ky/storage/route_store.py:165-182` 先发布 `route--r1.yaml`，再 `replace_bytes(manifest)`，后者失败无回滚。临时目录内用 `patch("ky.storage.route_store.replace_bytes", side_effect=OSError("manifest unavailable"))` 提交 r1：捕获异常后目录仍有 `route--r1.yaml`、无 manifest；再次提交 r1 又因目标文件存在而被拒绝。CLI 会把该 OSError 作为退出 2，但违反 `contracts/route_plan.md:17-21,29` 的“提交未写入”承诺，并使库无法按正常入口恢复。需明确失败原子性并清理本次新建版本，或采用能从未登记版本安全恢复的协议；崩溃窗口也应有可审计恢复办法。 |
| S4：版本文件“不可覆盖”只对配合锁的写者成立 | **必须改** | `ky/storage/route_store.py:159-162,184-199` 先 `exists()`，后 `os.replace()`；Windows 上后者会覆盖在间隙出现的目标。归档探针在 `os.replace(temp, route--r1.yaml)` 调用前模拟外部写者创建该路径并写入 `b"external writer"`，提交成功且该字节被覆盖。短暂 `.routes.lock` 只约束同类写者，不能使“目标文件已存在即拒绝、版本文件不可覆盖”成为文件系统级保证。应使用原子的不覆盖发布操作，或在规格中把保证明确收窄到遵守锁的写者并处理外部文件冲突；当前实现与绝对表述不符。 |

## 3. CLI 与注册表

| 项 | 判断 | 证据、可复现输入与处理建议 |
| --- | --- | --- |
| C1：正常输出、缺省存储、失败清理 | 不改（受 S2/S3 限制） | `ky/__main__.py:113-121,606-671`：显式 `--store` 优先；否则经 `_load_workspace_for_default` 和 `write_target("state.routes")`；成功 submit 打印路径、revision、SHA；show JSON 形状与规格一致。归档探针 `route show --json --store <不存在目录>` 输出 `null` 且退出 0；预置锁时退出 2。非法路线在进入存储前被拒且无文件；manifest 写失败的“无文件”反例见 S3。 |
| C2：输入文件不存在时的错误码受工作区解析顺序影响 | 建议改 | `ky/__main__.py:626-633` 先解析缺省 store，后检查 `--plan`。运行 `route submit --plan <不存在文件> --workspace <不存在注册表>` 实得退出 **2**（先报 workspace），而 `contracts/route_plan.md:29` 指定“输入文件不存在”退出 **3**。建议先检查 `--plan` 是否为文件，再查默认工作区；明确双重错误的优先级。 |
| R1：新增可选注册表键的影响 | 不改 | `kaoyan.workspace.yaml:60-65` 仅在 `state` 下增加 `routes: data/routes`；`contracts/workspace.md:111,227,287` 已声明为可选写入目标。归档内 `tests.contract.test_workspace` 运行 23 项（22 通过、1 跳过）；`tests.test_cli` 41 项通过。路线专属测试还用解析 YAML 后删除该键验证未登记提示，没有因复制注册表的测试辅助写死文本而失效。现有快照、投影和规划输入仍无消费 `state.routes` 的新逻辑，符合 E3a 范围。 |

## 4. 新测试的反向检验

| 项 | 判断 | 证据、可复现输入与处理建议 |
| --- | --- | --- |
| T1：任务书指定的核心断言 | 不改 | 固定归档分别运行 `py -3.12 -m unittest tests.contract.test_route_plan_port`（7/7）、`tests.test_planning`（19/19）、`tests.contract.test_workspace`（23/23，1 跳过）、`tests.test_cli`（41/41）。在**临时归档**逐一撤掉 `parse_route_plan` 末尾的 `validate_route_plan` 调用、SHA 比较、revision 比较，再各跑对应单条 `test_rejects_invalid_shape_types_and_closure_with_paths`、`test_tampered_revision_is_rejected`、`test_compare_and_swap_rejections_write_no_bytes`：三条均变红。未跑全量。 |
| T2：尚未受断言约束的存储承诺 | 建议改 | `tests/contract/test_route_plan_port.py:108-155,170-213` 只覆盖有效 manifest、版本内容 SHA 篡改、解析前拒绝的“不写”。在临时归档将 `_read_manifest` 的 `if raw.get("schema_version") != 1` 换成 `if False` 后，完整的**路线单模块**仍是 7/7 通过。路径越界、条目版本类型/顺序、manifest 写失败后残留、锁冲突和 `os.replace` 间隙均无对应断言。至少给 S2/S3/S4 的修复各加一条能在撤回检查时变红的定向回归测试。 |

**总体：FAIL。** 优先修 S2（可信 manifest 边界）和 S3（失败后留下孤儿版本），同时兑现 S4 的“不覆盖”语义；F2 是独立的 CLI 契约错误。锁的人工恢复及当前注册表登记可以保留。
