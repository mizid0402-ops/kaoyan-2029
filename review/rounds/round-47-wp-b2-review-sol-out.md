# Round 47 WP-B′2 投影独立评审：FAIL

范围：`341200b` 的 `ky/projection/`、`contracts/projection.md`、`tests/contract/test_projection_port.py`，并核对本次调整的既有投影测试。只在系统临时目录构造输入；没有重建仓库投影。`py -3.12 -m unittest tests.contract.test_projection_port -v`：**Ran 10 tests，OK**。全量未跑（按仓库 `AGENTS.md`，由决策者提交前统一跑）。

## 1. 两个指定问题

| 编号 | 判断 | 证据与最小处理 |
|---|---|---|
| M1 输入哈希和解析分两次读 | **必须改，MAJOR**。冻结数据是操作约定，不能证明同一轮构建期间文件不变；规格 `contracts/projection.md:64-66` 声明 `inputs` 是投影实际读取字节的 SHA-256，且 `:71-73` 要求同输入确定性。`ky/projection/__init__.py:109-125,147-160,180-182,206` 先对全部文件 `read_bytes()` 算哈希，再由树、附表、JSON 解析器重新打开文件。本机临时工作区在权重文件首次 `read_bytes()` 返回后立即写入另一份有效 JSON：构建成功、`topic_weights` 表取**新值**，`inputs` 却等于**旧字节**哈希而不等于新字节哈希。改为每个登记文件只读取一次原始字节，解析与哈希共用这份内容；知识点路径加载器可增设 bytes/stream 入口。加入哈希读取与解析之间文件变化的回归测试。 |
| D1 读树时使用 `writer="deterministic_script"` | **建议改；根因在既有知识点接口，本包扩大了不一致**。`ky/projection/__init__.py:35-36` 以可写频率的身份读树；快照 `ky/schedule/state_snapshot.py:103` 使用 `state_snapshot`，而 `ky/knowledge/knowledge_point.py:124-146,371-387` 把“谁可写入”用于读取时的校验。本机临时树给一个节点加入合法的 `frequency: {value: 1, computed_by: deterministic_script, ...}` 后，同一工作区投影成功、快照报 `KnowledgePointError ...frequency.value`。当前树均无该值时不影响本包现有结果；只把投影 writer 改成 `state_snapshot` 会使两者一起拒绝合法的已写频率，不能根治。最小的接口修法是拆开**已有数据的来源/形状校验**与**写入动作的权限校验**：只在 `apply_deterministic_frequency` 等变更入口检查 actor，两个读者共用无写权限语义的加载入口；再加同树双读者回归。此项单独不作为本轮 FAIL 门槛。 |

## 2. 规格逐条对照与其他缺陷

| 规格/事项 | 判断 | 证据 |
|---|---|---|
| §Inputs：注册表、优先级、必需文件、输出覆盖 | **不改**。`build_projection(workspace, out)` 不自行发现注册表，`ky/projection/__init__.py:80-107` 用 `require`/`require_all` 取登记输入，`:88` 选择输出；CLI `ky/projection/__main__.py:21-32` 使用 `load_workspace` 并捕获契约/知识树错误。`serve.py:44-58` 使用注册表默认路径或显式数据库路径。未见旧路径常量或目录 glob。 |
| §Inputs：无效输入须以契约错误失败 | **必须改，MAJOR（M2）**。`contracts/projection.md:28-33` 要求非法登记输入抛 `ContractError`（树可抛 `KnowledgePointError`）。临时工作区把已登记索引的首条 `locator` 改为 `[1]`，`build_projection` 实际抛 `AttributeError: 'list' object has no attribute 'get'`；CLI `ky/projection/__main__.py:30-32` 也不会转成 exit 2。触发点是 `ky/projection/__init__.py:193-202`：`locator.get` 的 `AttributeError` 不在捕获集合中。先校验 locator 为映射，再以该索引条目的字段路径抛 `ContractError`；增畸形 locator 的定向回归。 |
| §Effective/supplementary：只按同科生效 ID 判定补充节点 | **必须改，MAJOR（M3）**。生效树检查 ID 科目（`ky/projection/__init__.py:133-135`），补充树没有对应检查（`:152-174`）。临时工作区给 cs408 补充树和附表各加一个 `math1.synthetic.extra`，构建成功，SQL 查到该 ID 的 `subject_id='cs408', is_effective=0`。这使补充行的科目事实错误，违反 `contracts/projection.md:41-52` 所述“该 subject 的补充树”。校验每个补充节点的 ID 所属科目等于 `view.subject`，否则在 `supplementary.<name>.files.tree` 拒绝；加外科目节点回归。 |
| §Effective/supplementary：表分离、子集、附表 ID 对齐 | **不改**。`ky/projection/__init__.py:129-176,232-247` 把生效和补充节点分表、只在补充行拼附表属性，`:156-162` 检查子集与附表 ID 集；`tests/contract/test_projection_port.py:97-110,175-208` 覆盖仓库计数与三种集合失配。M3 是这组校验遗漏的同科约束。 |
| §表/视图/元数据/提示语 | **不改（M1 例外）**。七张表、三个视图、schema version 2、按科计数、补充视图列表、`workspace_registry_sha256`、跨年提示在 `ky/projection/__init__.py:232-295`；`inputs` 的值有 M1 的版本错配。 |
| §输入验证后才写、原子替换与纯读 | **不改**。`ky/projection/__init__.py:90-225` 处理输入，`:226-309` 才建目标目录/临时库并 `os.replace`。已登记索引缺失时旧投影字节不变，见 `tests/contract/test_projection_port.py:163-173`；本轮探针没有写仓库参考数据。 |
| 契约测试断言强度 | **建议改**。`tests/contract/test_projection_port.py:210-225` 的“内容确定性”只比较元数据，没有比较表行；仓库有效/补充测试 `:97-110` 只以行数和 `LIKE '%legacy-item%'` 检查 7 个节点，未核对完整 ID 集和各 `tree_source` 精确登记键。替换测试 `:125-161` 只复制不改内容，因而无法发现“元数据用新路径、解析仍读旧路径”的实现。现有 `tests/test_projection.py` 有同库重建的字节一致性断言，但不覆盖替换路径后的表内容。M1/M2/M3 的精确触发输入应各有回归测试；其他断言增强可随之安排。 |

## 3. 门禁结论

**FAIL。** M1 使投影内容与来源哈希不对应；M2 使无效登记输入逃逸契约错误边界；M3 把外科目节点写成补充视图科目。三项都有系统临时目录中的实际触发与确定结果。D1 是知识点读写身份混用的既有问题，建议另列接口修订，不把仅改投影 writer 当作修复。若怀疑影响其他模块，优先关注 `ky.knowledge` 与 `ky.schedule.state_snapshot` 的频率读取语义；本轮未运行其测试模块或全量测试。
