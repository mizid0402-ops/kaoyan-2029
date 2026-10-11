# Round 83 Codex 复审

基线：`git archive 904c37f` 解到系统临时目录，复制了 Git 忽略的 `data/raw_materials/`。仅在临时归档和系统临时目录运行探针；未跑全量测试。第 80 轮的 B1/B4/B5/B6 指该轮报告中的原编号。归档无 `.git`，运行含固定旧版基线的测试时设置 `GIT_DIR=F:/workspace/kaoyan-ai-system/.git`，供 `git show 11cda18:...` 读取旧代码。

## 一、`2e53d6e`：B4 投影层级

| 项 | 意见 | 证据与可复现输入 |
| --- | --- | --- |
| P1 原复现与重建产物 | 不改 | `ky/projection/__init__.py:226,275` 的生效表、补充表均用 `ky.knowledge.parent_id`。`git rev-parse` 确认 `11cda18` 的旧 SQLite 与 `2e53d6e^` 中的旧 SQLite 是同一 blob；将它与 `904c37f` 归档中的新 SQLite 按主键连接，以 `n.parent_id IS NOT o.parent_id` 计数，得到生效表 cs408 **38**、eng1 **4**、math1 **0**，补充表 cs408 **38**。在临时目录用新代码再执行 `build_projection(load_workspace(...), 临时库)`，两张表的 `(主键,parent_id,depth)` 与提交的 SQLite 全行相等。第 80 轮“缺中间前缀”节点如今能获得较远的现存父节点；`tests/contract/test_projection_port.py:116-151` 同时断言两张表。 |
| P2 schema 版本 | 建议改 | `contracts/projection.md:64` 和 `ky/projection/__init__.py:515` 仍为 schema 2；列、类型、表结构未变，**按结构版本理解时不升版成立**。但 `parent_id` 的语义在同一 schema 2 下变了；旧、新库的 `inputs` 元数据相同，实测元数据仅 `workspace_registry_sha256` 不同（同期注册表改动），它并非算法版本。若下游用 schema 版本识别父节点语义，将无法区分旧 v2 与新 v2。建议在契约定义 schema 与语义版本的边界，或另记投影规则版本；本次已重建仓库产物，不据此阻断。 |
| P3 `depth` 含义 | 建议改 | `ky/projection/__init__.py:225-237,274-285` 继续写 `len(point_id.split('.')) - 1`；这不是沿 `parent_id` 走到根的边数。例如新库的 `cs408.cn.chapter-01` 为 `parent_id=NULL, depth=2`。这在修复前也成立，保持数值不变合理，但 `contracts/projection.md:50,52` 只列 `depth INTEGER`，未定义含义。建议明写“ID 点分段数减一”，避免消费者把它当图深度；无需为此改变既有值。 |
| P4 撤修复测试 | 不改 | `py -3.12 -m unittest tests.contract.test_projection_port`：14/14 通过；新增两条层级端口精确测试：2/2 通过。临时把投影引用的 `parent_id` 换回“只找紧邻前缀”，`test_projection_parent_uses_port_across_missing_intermediate_prefix` 变红；把知识树端口换回同一错误，两条新增端口测试均变红。 |

**`2e53d6e`：PASS。**

## 二、`904c37f`：B1、B5、B6 及 B2、B8

| 项 | 意见 | 证据与可复现输入 |
| --- | --- | --- |
| W1 B1 原复现 | 不改 | `tools/aggregate_topic_weights.py:54-103,162-185` 仅在 `--check` 读旧产物；`--write` 从清单、编码产出及生效树计算。`tests/contract/test_topic_weights_port.py:360-381` 分别将旧 JSON 损坏和移除，`--write` 均成功，随后 `--check` 成功。把临时归档工具的 `read_current=args.check` 撤成恒真，这两条测试各失败一次。原 B1 已关闭。 |
| W2 写入目标的硬链接别名 | **必须改** | `_write_target()` 以 `resolve(strict=False)`、`relative_to(root)` 判定目标（`tools/aggregate_topic_weights.py:107-119`），再对该路径 `write_text`（`:180-185`）。复现：在系统临时目录建立工作区和其外的 `outside.json`（内容 `outside sentinel`）；在工作区内用 `os.link(outside, hardlink.json)` 建 NTFS 硬链接，把注册表 `reference.topic_weights` 设为 `hardlink.json`，执行 `--write --workspace <该注册表>`。实测退出 **0**，且工作区外 `outside.json` 被重算产物覆盖，`os.path.samefile` 仍为真。路径 `resolve` 无法识别硬链接的另一个名字，故“目标留在工作区内”不足以保证写入效果不越界。建议在已校验的工作区内父目录创建临时文件，再以 `os.replace` 替换目标；这样已有硬链接会被拆开，外部文件不被原位改写，并补该输入的回归。 |
| W3 缺失文件与 junction | 不改 | 普通缺失目标由 W1 的测试证明可创建。另在临时工作区把 `junction/` 指向工作区外目录，登记 `reference.topic_weights: junction/topic_weights.json`（末端文件不存在），运行 `--write`：退出 **2**，报 `reference.topic_weights: resolves outside the workspace`，外部目录没有产生文件。此路径规则能处理实测的父目录 junction；W2 是不同的文件别名漏洞。映射盘符、竞争性换链未实测。 |
| W4 B5 身份 | 不改 | `ky/exam/topic_weights.py:76-87` 拒绝布尔／非四位整数年份，来源码用 `^[a-z][a-z0-9]*$` 全匹配，缺省 `national`，与 `contracts/topic_weights.md:33-40` 一致。原输入：批次与编码者年份同步改 `1`、来源改 `school-x` 均抛 `ContractError`；合法 `xidian` 产生自命题键。`tests/contract/test_topic_weights_port.py:330-359` 对应正反例通过；临时撤掉身份检查，两个负例各变红。 |
| W5 B2 措辞 | 建议改 | 明写 `0.0 == -0.0` 且不用容差（`contracts/topic_weights.md:72-78`），比“逐位相等”准确；但“数值相等”还不完全精确：`_differences({'x':1.0},{'x':1})` 报 `JSON types differ (float != int)`，尽管 Python 数值比较相等（`tools/aggregate_topic_weights.py:121-147`）。建议把规格改成“JSON 类型相同，数值比较无容差；有符号零视为相等”，或明确允许整数／浮点跨类型相等。当前产物检查不受影响。 |
| W6 B8 措辞 | 不改 | 已写清空／null `nodes` 可省 `confidence`（`contracts/topic_weights.md:49-55`），实现对缺少 `nodes` 字段报错、对空列表不投票（`ky/exam/topic_weights.py:185-230`），相符。删除一条已有编码记录的 `nodes` 字段，聚合报 `batches[0].sol.1.nodes: required field is missing`；这不同于显式空列表。 |
| W7 B6 键解析与写回 | 不改 | `tools/apply_knowledge_weights.py:51-72` 以 3 段统考键和 4 段自命题键区分；注册表科目 ID 与出题单位代码均不含连字符（`ky/workspace.py:45,430`；`contracts/topic_weights.md:36-38`），年份固定四位，三者之间无解析歧义。`apply_to_index` 用 `(subject,year,paper_source,number)` 匹配，索引缺省来源为 `national`（`tools/apply_knowledge_weights.py:114-132`）。临时同时登记统考／`xidian` 两份索引，仅有 `cs408-xidian-2023-1` 权重时，只写学校卷；把自命题解析正则撤掉，`test_school_paper_key_writes_to_matching_index` 报错变红。原 B6 已关闭。 |
| W8 只写登记索引与旧版对照 | 建议改 | `_registered_indexes()` 只取 `reference.exam_indexes` 的 `require_all`（`tools/apply_knowledge_weights.py:104-112,180`），符合注册表为生效数据源的规则；临时工作区登记 `national.json`，同目录再放未登记、同身份的 `stray.json`，工具退出 0、写了登记文件、`stray.json` 逐字节不变。`test_national_index_bytes_match_fixed_baseline`（`tests/contract/test_topic_weights_port.py:429-455`）固定 `11cda18`，断言旧解析器标记，在两份独立临时副本运行旧／新工具，并比较全部索引原始字节；本机通过，方法可信。**测试缺口**：学校卷测试目录里没有未登记诱饵；临时把 `_registered_indexes` 撤成扫描 `*.json`，该测试仍绿。建议加一份未登记诱饵并断言其字节不变，防止以后悄悄恢复目录扫描。 |
| W9 定向验收 | 不改 | 临时归档：`py -3.12 -m unittest tests.contract.test_topic_weights_port` 为 13/13 通过；`py -3.12 tools/aggregate_topic_weights.py --check` 返回 `matches registered batches (numeric equality, no tolerance; 0.0 == -0.0)`。仅测试所需模块，未跑全量。 |

**`904c37f`：FAIL。** 原 B1/B5/B6 的复现已关闭；新确认的硬链接目标会使 `--write` 改写工作区外文件，属于写入边界缺陷。

## 结论

**整体 FAIL**：投影层级修复可通过；权重包需先关闭 W2。W5、W8 为非阻断的规格／测试建议。
