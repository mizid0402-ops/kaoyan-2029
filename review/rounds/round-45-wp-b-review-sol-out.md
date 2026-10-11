# Round 45 WP-B 实现审查：FAIL

范围：`git show f3539b8` 的注册表、加载器、契约测试及 `contracts/workspace.md`。只读；运行 `py -3.12 -m unittest tests.contract.test_workspace -v`：**9 项通过，1 个符号链接子用例跳过**。未跑全量测试，也未审查正在并行修改的快照模块。

## 1. 规格逐条对照

| 规格 | 结论 | 证据与意见 |
|---|---|---|
| §2.1 字段、结构、错误路径 | **必须改** | 必填/可选、类型、未知键、科目与补充角色的主体校验已实现：`ky/workspace.py:27-37,275-391`，样例在 `kaoyan.workspace.yaml:1-43`。但重复键的字段路径可报到**另一个字段**（M1），且 Windows 大小写别名可重复登记同一索引文件（M2）；分别违反 `contracts/workspace.md:79,99-101`。 |
| §2.2 被登记路径语法 | **不改** | `_registered_path` 在 `ky/workspace.py:202-212` 拒绝空段、`.`、`..`、反斜杠、冒号和绝对路径，按注册表父目录构造路径；与 `contracts/workspace.md:103-116` 一致。 |
| §2.3 内嵌路径基准 | **不改** | `Workspace.root` 暴露注册表父目录（`ky/workspace.py:262,394-395`）；本 WP 不读台账/树/索引内容，符合 `contracts/workspace.md:118-121`，实际消费方仍须在 WP-B′ 落实。 |
| §2.4 补充视图 | **不改** | `ky/workspace.py:335-359` 限定 `cross_year_tree` 恰有 `tree`、`agreement`；超集关系及生效/补充投影隔离由消费方检查，符合 `contracts/workspace.md:123-133`。 |
| §3.1 发现 | **不改** | `ky/workspace.py:140-179,255-262` 实现显式 > `KY_WORKSPACE` > 最近向上、空环境值当未设置、选定后失败不回退。`--workspace` CLI 参数本 WP 暂不添加，规格 §8 明确后移。 |
| §4 存在性/越界 | **不改** | `ky/workspace.py:93-137` 加载时不检查登记文件，`require/require_all` 按键、存在、F/D 类型及真实路径边界检查；写入目标不走 `require`。Windows 本机 junction 越界测试通过。大小写、设备前缀与映射盘符的适用限度见第 3 节。 |
| §5 输入指纹 | **必须改** | `ky/workspace.py:265,269,396` 先 `read_bytes()` 算哈希，随后 `_read_yaml_file(source)` 再读一次。两次之间文件变化会令哈希与已加载路径不对应（M3）；违反 `contracts/workspace.md:167-170` 的来源版本含义。 |
| §6 Python 接口 | **建议改** | 字段、冻结 dataclass、嵌套只读映射、列表元组和 `ContractError` 基本一致（`ky/workspace.py:40-69,219-221,328-329,357-359,393-420`）。但 YAML 语法错误由共享加载器抛出的 `ContractError.path` 可为空；“所有错误带字段路径”（`contracts/workspace.md:220`）对无法定位到字段的语法错误应明确采用文件级路径或例外，避免替换实现各自解释。 |

## 2. `_duplicate_field_path`：有确定的错误路径

**M1 — MAJOR / 必须改。**位置：`ky/workspace.py:231-253,268-274`。触发：合法 YAML 写法中的父键加引号，例如完整注册表把 `reference:` 改为 `"reference":`，并在其下写两次 `topic_weights`。本机系统临时目录复现：`load_workspace` 报 `ContractError.path == 'subjects.topic_weights'`，实际重复字段是 `reference.topic_weights`。原因是逐行正则不认带引号的父键，栈里残留前一个顶层 `subjects`。另一例 `reference: {topic_weights: a, topic_weights: b}` 报 `reference`，而非 `reference.topic_weights`；列表内映射重复也会丢掉索引。预期：重复仍被拒绝，路径指向真实重复字段。最小修法：在 YAML 节点树构造时携带祖先路径（或返回结构化重复错误），不要从文本正则倒推；补引号父键和行内映射的回归测试。

## 3. `require()` 的 Windows 边界

**不改（已验证的普通路径）。**`Path.resolve(strict=True)` 对登记路径与根都执行，`relative_to` 的 Windows 比较不区分普通大小写。本机用原大小写、全小写、`\\?\F:\…` 三种注册表路径加载并 `require('reference.topic_weights')` 均成功；当前契约测试还用 junction 指向根外并确认拒绝（`tests/contract/test_workspace.py:229-245`）。

**建议改（边界说明/补测试）。**`F:\…` 与 `\\?\F:\…` 即使指同一实体，直接交叉做 `relative_to` 也会因不同锚点失败；当前实现由同一 `Workspace.root` 派生目标，两边解析后前缀一致，所以我没有复现 `require` 误拒。映射盘符环境本机未核实，不能断言“所有映射盘符可靠”；如列为正式支持场景，应在该环境加根、目标同映射盘符及 junction 越界测试。`require()` 验证后才由消费方打开文件，不能把此检查宣传为抵御并发替换 junction 的授权沙箱。

另有独立于 `require` 的 **M2 — MAJOR / 必须改**：`ky/workspace.py:310-327` 用 `str(value)` 的区分大小写集合判断索引重复。本机验证现有 `408_index_2023.json` 与 `408_INDEX_2023.JSON` 是同一文件；把 `data/index.json` 与 `data/INDEX.json` 同时写进索引列表，加载器却接受两个条目。预期按 `contracts/workspace.md:79` 拒绝同一路径；修法是对 Windows 路径使用规范化大小写的词法键，并保留逐项原始路径供错误定位。回归测试须覆盖同列表及跨科目大小写别名。

## 4. 契约测试的弱断言

- **必须改｜M1/M2/M3 回归**：`tests/contract/test_workspace.py:151-171` 仅测普通未加引号的块式重复键；`144-145` 仅测字节完全相同的索引路径；`325-335` 只测静态文件哈希。三类反例已实测。M3 的复现是在系统临时目录于两次读取之间改写注册表：加载到 `changed.json`，返回的 `sha256` 却等于旧文件而不等于当前文件。应只解析一次读到的字节，或读后复核同版本并失败/重试。
- **建议改｜错误路径断言过宽**：`tests/contract/test_workspace.py:156-164` 对多数拒绝用例使用 `assertIn(expected_field, actual_path)`；例如未知树科目只期待 `reference.knowledge_trees`，错误实现若只报父节点也能过。规格说字段路径是契约（`contracts/workspace.md:101,227`），应对每个确定位置用 `assertEqual`，列表项明确到 `[index]`。
- **建议改｜错误类别和路径值未测**：`tests/contract/test_workspace.py:200-218` 的缺失、F/D 类型错多只断言 `ContractError.path`；全部统一报“not registered”也可能通过这些负例。应断言缺失消息含解析后路径，类型错可区分文件/目录。`test_1_repository_registry` 的 `require_all` 只调用未核对返回的 11 个具体路径（同文件 `73-98`）。
- **建议改｜跳过范围缩小**：`tests/contract/test_workspace.py:250-263` 在一个大测试末尾调用 `skipTest`，使整项显示 skipped，尽管前面的 junction 断言已执行。拆为独立符号链接测试可让 Windows 验证记录更准确。

## 5. 其余阻断项与门禁

**M3 — MAJOR / 必须改。**位置：`ky/workspace.py:264-270,393-396`。触发：另一进程在原始字节读取后、YAML 解析前更新注册表。本机用临时文件和读取间钩子复现：`workspace.topic_weights.name == 'changed.json'`，`workspace.sha256` 却是旧内容的哈希。预期哈希指认本次解析出的同一份字节；将解析与哈希绑定到一次读取，并加受控两次读取变化的回归测试。

**门禁：FAIL。**本轮无数据写入或普通路径崩溃；但 M1、M2、M3 分别违反必需的诊断路径、索引去重和输入指纹契约。修完这三项并运行 `py -3.12 -m unittest tests.contract.test_workspace` 后，按同一范围复审即可；不需要全量测试。

### 修复包

1. **M1**：用 YAML 节点位置信息生成真实字段路径；加带引号父键与行内映射重复键测试。
2. **M2**：Windows 下以同文件语义去重索引路径；加大小写别名的同科、跨科测试。
3. **M3**：用同一份字节计算哈希和解析内容；加读取间文件变化测试，保证返回值同版本或明确失败。

仅改上述阻断项及直接回归测试；修复后执行工作区契约测试并给出结果。

## 复审（9dc9191）：FAIL

范围只限 M1/M2/M3 的修复、回归测试和直接引入的问题。`py -3.12 -m unittest tests.contract.test_workspace -v`：**12 项，OK，1 个符号链接子用例因权限跳过**；未跑全量测试。

| 上轮问题 | 状态 | 证据 |
|---|---|---|
| M1 重复键错误路径 | **已修复** | `ky/workspace.py:233-268` 改为遍历 YAML 节点；原引号父键和行内映射触发分别得到 `reference.topic_weights`、`materials.raw_root`。`tests/contract/test_workspace.py:151-172` 加了精确路径回归。 |
| M2 Windows 大小写索引别名 | **已修复** | `ky/workspace.py:329-336` 用 `os.path.normcase` 去重；原 `data/index.json`/`data/INDEX.json` 触发 `reference.exam_indexes.cs408[1]`；同科和跨科测试见 `tests/contract/test_workspace.py:276-290`。 |
| M3 哈希/解析两次读取 | **已修复** | `ky/workspace.py:256-268,279-283` 只读一次原始字节并解析同一份内容；读取后替换临时文件的回归测试得到旧路径 `first.json` 与旧字节哈希一致（`tests/contract/test_workspace.py:292-315`）。 |

**新发现 M4 — MAJOR / 必须改：循环 YAML 别名导致非受控 `RecursionError`。**位置：`ky/workspace.py:233-253,263-268`，由 M1 新增的节点树遍历直接引入。触发文件可只含：

```yaml
schema_version: 1
subjects: [cs408]
reference: &x
  self: *x
```

这是可解析的 YAML；原共享 `_read_yaml_file` 能读出自引用映射。本机在系统临时目录调用 `load_workspace`，实际抛出 `RecursionError: maximum recursion depth exceeded`，而规格 `contracts/workspace.md:98-101,220` 要求非法注册表以 `ContractError` 受控拒绝。原因是别名令节点图成环，`_reject_duplicate_keys` 没有访问中/已访问节点集合。最小修法：检测环并抛文件级或相应字段路径的 `ContractError`，或安全地跳过已访问节点后让结构校验拒绝 `reference.self`；加该精确输入的回归测试，断言 `ContractError` 而无 traceback。

**复审门禁：FAIL。**M1/M2/M3 已解决，但 M4 是修复直接造成的 MAJOR 回归。下一轮只需检查 M4 及其测试，复跑工作区契约测试；无须重新审整份注册表或跑全量测试。

## 第三次复审（63efad7）：PASS

**M4 已修复。**`ky/workspace.py:233-261` 在遍历 YAML 节点图时记录已访问节点，遇到自引用别名不再递归进入同一节点；其后 `load_workspace` 的结构校验在 `ky/workspace.py:317-318` 拒绝未知字段 `reference.self`。`tests/contract/test_workspace.py:176-185` 使用上轮给出的精确输入，对两个加载入口均断言 `ContractError.path == "reference.self"`。

本机运行 `py -3.12 -m unittest tests.contract.test_workspace -v`：**Ran 13 tests，OK（skipped=1）**；跳过的是当前账户缺少符号链接创建权限的子用例，junction 子用例已执行。检查本次节点遍历改动及其回归测试，未发现新的阻断问题。本结论只覆盖 M4 修复范围，未跑全量测试。
