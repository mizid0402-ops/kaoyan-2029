# `verify_tree.py` 静默降级修改建议（Codex）

日期：2026-09-15  
范围：只针对“chapter 全删或全部改 scope 后，cs408 被静默识别成 structure 并通过”这一项缺陷；不讨论未复现的 P16、P7、P8。

## 结论

推荐采用“**完整 ID 集合先选定显式 profile，scope 只负责交叉校验**”的方案：

1. 不再以 `scope == "chapter"` 的存在性选择检查分支。
2. 从所有 `knowledge_point_id` 的首段命名空间识别唯一 profile：`cs408 -> cs408`、`math1 -> math1`、`eng1 -> structure`。
3. 所有 ID 必须属于同一已支持命名空间；混合或未知命名空间直接报 `TreeShapeError`，不得回退到 structure。
4. profile 选定后，再按该 profile 的 ID 语法与 scope 分布做双向校验。ID 决定“应当是什么”，scope 证明“实际标注正确”。

不推荐“扫描 chapter scope，若没有就当 structure”；也不推荐仅把现有 marker 从 chapter 节点扩大到 section 节点后继续保留“无 marker 即 structure”的负向兜底。后者虽能修 P1/P3，仍会把未知或被破坏的树当作 structure。把 `eng1` 也变成一个显式的正向 profile，才能消除静默分支。

## 已确认事实

- 共同底本共 103 行，SHA-256 为 `DF6880F12AF3B3AC23120E5EF08AF79391E2907C35C6DB46B998364F37EA1D8F`。
- 当前 `infer_tree_shape()` 先过滤 `scope == "chapter"`；过滤结果为空便返回 `structure`（`tools/verify_tree.py:58-60`）。
- 我做了不落盘的内存探针：cs408 基线为 403 节点、识别为 `cs408`；去掉全部 24 个 chapter 后为 379 节点、识别为 `structure`；保留节点但把 24 个 chapter scope 改成 section 后仍为 403 节点、识别为 `structure`。
- 当前完整 ID/scope 分布：

| 文件 | 根命名空间 | scope 分布 | 可从全部 ID 得到的正向结构签名 |
|---|---|---|---|
| cs408 基线 | 仅 `cs408` | subject 20 / chapter 24 / section 116 / item 243 | 24 个 `cs408.<domain>.chapter-NN` 锚点；其下有 `section-NN` |
| cs408 多源主表 | 仅 `cs408` | subject 20 / chapter 24 / section 116 / item 250 | 同上，24 个章锚点 |
| math1 | 仅 `math1` | subject 3 / chapter 22 / section 44 | 22 个 base，每个都有 `.chapter/.content/.requirements` 三元组 |
| eng1 | 仅 `eng1` | section 13 / item 11 | 无 chapter 家族；是显式 `eng1` structure profile，不是缺省分支 |

- 我只读重跑四棵真实树，四条命令均 `exit=0` 且有 `ALL CHECKS PASSED`。当前文件哈希如下：

| 文件 | SHA-256 |
|---|---|
| `tools/verify_tree.py` | `A3FA06F96FE5670EC146DB3414FF3AC4A37EBDF0268C405F1B7E3C1896259C3A` |
| cs408 基线 | `A535394DAFE21681C974F3114C3A20CDCC090403CA4B05665903DCBF48008418` |
| cs408 多源主表 | `D9D3238EE9722B46E4D89188BB84D4D9F54F83BDEFDD385A635694FC268B74A1` |
| math1 | `A6657D2C6F64DA6B91FCF0AE5E97C625FA15055D9BF2D87EFC5901B6C73845B5` |
| eng1 | `65E2AA730FD02B2E400BD95BD90361BC840187BF36029F6BBCD582E9D0156129` |

以上是实测；下面是建议设计与预期行为，尚未实现。

## 可直接实现的分类与守卫

### 1. profile 识别

把 `infer_tree_shape(points)` 改成以下确定性流程（函数名可以保留）：

```python
SUPPORTED_ROOT_SHAPES = {
    "cs408": "cs408",
    "math1": "math1",
    "eng1": "structure",
}

ids = [p.knowledge_point_id for p in points]
roots = {pid.split(".", 1)[0] for pid in ids if "." in pid}
if len(roots) != 1:
    raise TreeShapeError(f"mixed or missing tree namespaces: {sorted(roots)}")
root = next(iter(roots))
if root not in SUPPORTED_ROOT_SHAPES:
    raise TreeShapeError(f"unsupported tree namespace: {root!r}")
tree_shape = SUPPORTED_ROOT_SHAPES[root]
```

这里 scope 完全不参与分支选择。`scope` 被全删、全改或局部改坏，都不会把 cs408/math1 切换成 structure。

### 2. cs408 profile

从**全部 ID**而非 chapter-scope 子集提取章锚点：

- 章锚点：`^cs408\.[^.]+\.chapter-[0-9]{2}$`
- 章后代：`^(cs408\.[^.]+\.chapter-[0-9]{2})(?:\.|$)`，捕获组即应存在的章锚点。
- section：`^cs408\.[^.]+\.chapter-[0-9]{2}\.section-[0-9]{2}$`

必须同时满足：

- 至少能从完整 ID 集合导出一个章锚点，否则报 `cs408 profile has no chapter-family ids`。
- 每个由自身或后代导出的章锚点 ID 都存在，且其 scope 恰为 `chapter`。不存在时报 `missing cs408 chapter anchor <id>`；存在但标签错误时报 `<id>: expected scope chapter, got <scope>`。
- 每个 `scope == chapter` 的节点都匹配章锚点语法。
- 每个 `scope == section` 的节点都匹配 section 语法，并且直接章锚点存在且 scope 为 chapter。保留现有“单删一个章变红”的守卫。
- scope 集合只允许 `{subject, chapter, section, item}`，且 chapter、section 均非零。不要在验证器中硬编码 20/24/116/243 等数据量；精确数量继续由数据完整性测试锁定。

这会给“本该有章却没有章”一个独立、可定位的错误，而不是让后续分支偶然报错。P1 会报 24 个缺失章锚点；P3 会报 24 个章锚点 scope 错误。

### 3. math1 profile

从全部 ID 匹配 `^(math1\.[^.]+\.ch[0-9]{2})\.(chapter|content|requirements)$`，以捕获的 base 建组。每个 base 必须恰有：

- `<base>.chapter`，scope 为 `chapter`；
- `<base>.content`，scope 为 `section`；
- `<base>.requirements`，scope 为 `section`。

同时要求 scope 集合只允许 `{subject, chapter, section}`，chapter、section 均非零；所有 chapter-scope ID 均须以 `.chapter` 结尾。这样 math1 的“全删 chapter”与“全改 chapter scope”也不会降级。现有“缺一个 content”守卫继续保留，不放宽。

### 4. eng1 structure profile

structure 不再是“其他情况”的别名，只能由单一 `eng1` 根命名空间选中。随后要求：

- scope 集合只允许 `{section, item}`，两者均非零；chapter 和 subject 均为零；
- ID 中不得出现 cs408 的 `.chapter-NN` 家族，也不得出现 math1 的 `.chapter/.content/.requirements` 角色三元组语法；出现即报 profile 冲突；
- 保留当前 item 父路径检查，不借本修复扩大或放宽它。

### 5. 混合、未知与识别不明确

以下全部是失败，不允许尝试另一个分支：

- ID 根命名空间为空、超过一个或不在支持表中；
- profile 与外来 chapter 语法同时出现；
- profile 已确定但其必要 ID/scope 签名不成立。

建议在输出中把“profile 识别失败”与“profile 已识别、交叉校验失败”分开。前者打印 `tree shape: INVALID`；后者仍打印已识别的 profile，并列出具体缺失/错标节点。这样 P1/P3 的诊断不会被含糊地归为 unknown。

## 最小验证方案

只扩充 `tests/test_verify_tree_shapes.py`，不必先跑 248 项全套。每个 CLI 探针都应：确认变异不是 no-op；让 contract/hash/quote_ref 先通过；断言 `returncode != 0`、命中特定结构错误、且输出不含 `ALL CHECKS PASSED`。不能只断言“非零”，否则可能由无关错误误绿。

| 探针 | 临时副本上的具体构造 | 必须命中的真守卫 |
|---|---|---|
| C1（原 P1） | cs408 基线删除全部 24 个 `scope=chapter` 节点，保留 section/item | 仍打印 `tree shape: cs408`；命中 `missing cs408 chapter anchor` |
| C2（原 P3） | 不删节点，把全部 24 个章节点 scope 改成 section | 仍打印 `tree shape: cs408`；命中 `expected scope chapter, got section` |
| C3（控制组） | 仅删 `cs408.ds.chapter-01` | 命中该锚点缺失或现有 `section has no direct chapter-NN ancestor` |
| M1 | math1 删除全部 22 个 `.chapter` 节点，保留 content/requirements | 仍打印 `tree shape: math1`；命中 `missing ... .chapter` |
| M2 | math1 保留节点，把全部 `.chapter` 节点 scope 改成 section | 仍打印 `tree shape: math1`；命中 chapter scope 错误 |
| A1 | 在 cs408 副本中只把一个 ID 的首段改成 `math1` | 命中 `mixed ... namespaces` |
| A2 | 把 eng1 副本所有 ID 的首段统一改成 `other` | 命中 `unsupported tree namespace`，不得识别为 structure |
| E1 | 把一个 eng1 section ID 改成 `eng1.x.chapter-01`，scope 仍为 section | 命中 structure profile 的外来 chapter 语法冲突 |

哈希与隔离要求：

1. `setUp` 对四棵真实树计算完整 SHA-256；每条探针只用 `TemporaryDirectory`/`NamedTemporaryFile` 写副本。
2. `tearDown` 对四棵真实树重新计算完整 SHA-256并逐项相等断言；每个 probe 都获得自己的前后哈希证明，而不是只在整套结束后口头声称“未修改”。
3. subprocess 显式传 UTF-8，并断言 mutation 前后内容不相等，防止 no-op 探针。
4. 目标测试命令：`py -3.12 -m unittest tests.test_verify_tree_shapes -v`。
5. 目标测试通过后，只重跑四条真实树 CLI（cs408 基线、cs408 多源主表、math1、eng1），要求 `exit=0`、profile 正确且有 `ALL CHECKS PASSED`。按最小范围验证原则，此缺陷无需先跑全套 discovery。

## 为什么不会新增当前四棵树的误报

- 两棵 cs408 文件的全部 ID 都只有 `cs408` 根，并已有 24 个合法章锚点、116 个合法 section；新规则只是把现有事实写成显式不变量。
- math1 全部 ID 只有 `math1` 根，已实测 22 个完整的 chapter/content/requirements 三元组；新规则与现有数据一致。
- eng1 全部 ID 只有 `eng1` 根，scope 恰为 section 13、item 11，且没有两类 chapter 语法；它由显式 profile 进入 structure，不依赖缺省兜底。
- 不改 contract、source hash、quote_ref、provenance hygiene，也不改已修正的 subject 同级规则，因此不会回退 round-31 已消除的 220 条误报。

“不会误报”在实现前仍是推断，不能当作已验证事实；实现后必须以上述目标测试和四条真实树命令兑现。

## 明确不做

- 不改任何 `data/**` 文件，不改知识树 ID 或 scope 来迁就验证器。
- 不处理未复现的 P16，也不借机重写 structure 的 item 父路径算法。
- 不改 source/hash/quote_ref/状态流转检查。
- 不在生产验证器中硬编码四棵文件的精确节点数；精确数据量属于回归锁，不属于 shape 识别。
- 不把 `--require-scopes` 当修复。它依赖调用者记得传参，默认调用仍会静默降级。
- 不引入“未知即 structure”兼容模式；新增学科必须显式注册 profile 和测试。
- 最小目标测试与四棵真实树均通过前，不需要扩大到全套测试或做无关重构。

## 不确定项与边界

1. **无法仅凭树内数据证明历史意图。** 如果有人把整棵 cs408 的所有 ID、根命名空间和 scope 一致改写成一棵完全合法的 eng1 结构树，任何只看该文件内容的分类器都无法知道它“原来应该是 cs408”。本建议只保证 P1/P3 这类 scope/章节点破坏不会降级。若威胁模型要求抵抗整树一致改写，必须增加树外的可信期望（例如必填 `--expected-shape` 或受控 manifest）；这会改变 CLI 契约，建议另立任务。
2. **命名空间是否是正式稳定契约，仓库当前没有独立 schema 声明。** 四棵现有树的完整 ID 集合都支持该判断，且当前验证器已硬编码 cs408/math1 语法；但在实现前应由主控确认未来是否允许同一 shape 的新学科根。如果允许，应把 profile 表设计为可显式扩展，而不是恢复通用 fallback。
3. **exact scope 集合是否允许未来演进尚未确认。** 本建议按当前四棵真实树收紧；新增 item 到 math1 或 subject 到 eng1 应先更新设计与 profile 测试，不能由验证器静默接纳。
4. 我没有读取或比较 Claude 的独立建议，也没有修改仓库文件；本文仅依据共同底本、当前实现、现有测试和只读实测形成。
