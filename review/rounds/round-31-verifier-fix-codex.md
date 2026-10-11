# Round 31 验证器树形修复报告（Codex）

## 1. 三种树形的严格区分

实现位于 `tools/verify_tree.py` 的 `infer_tree_shape(points)`：

- `structure`：完整节点集中不存在 `scope=chapter`。
- `cs408`：至少一个 chapter id 完整匹配 `^[^.]+\.[^.]+\.chapter-[0-9]{2}$`，且所有 chapter id 都必须匹配；任一不匹配即拒绝。section 还必须完整匹配 `^.+\.chapter-[0-9]{2}\.section-[0-9]{2}$`，其去掉最后一段后的直接前缀必须存在且为 `scope=chapter`。
- `math1`：至少一个 chapter id 以 `.chapter` 结尾，且所有 chapter id 都必须以 `.chapter` 结尾；section 继续使用 `<base>.chapter` 祖先规则，每个 chapter 继续强制要求 `<base>.content` 与 `<base>.requirements`。
- cs408 标记与 math1 标记同时存在时，报 `ambiguous chapter tree`；存在 chapter 但两种标记均不存在时，报 `unrecognized chapter tree`。不使用分支顺序猜测。

## 2. subject 规则

实现位于 `subject_scope_failures(points)`：

1. 用 `candidate.knowledge_point_id != point.knowledge_point_id` 按 id 排除自身，不再依赖对象身份。
2. 相同父前缀、相同 `scope=subject` 的节点视为语义同层级，不报“必须更窄”。
3. 未来若出现比 subject 更宽的 rank，仍报错。
4. 若同 scope 节点的直接父前缀就是当前 subject id，则它是真正的直接子节点，仍报“必须更窄”。
5. chapter 的整棵真实 id 子树仍执行原有 rank 检查，因此 section 下塞入 `scope=subject` 的节点仍被拒绝。

这没有删除结构检查：math1 二件套仍是硬约束；cs408 section 必须有直接 `chapter-NN` 父前缀；未知或混合树形拒绝；subject 真直接子节点以及 chapter 子树中的过宽 scope 仍拒绝。改变的只是把同层级 subject 节点从错误的“子树”集合中分离。

## 3. 五条完成标准的实际输出

### 3.1 cs408 基线树

命令：

```text
py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree.yaml
```

实际结果：退出码 0；`contract: OK (403 nodes)`；`tree shape: cs408`；`structure: {'subject': 20, 'chapter': 24, 'section': 116, 'item': 243}`；`ALL CHECKS PASSED`。

### 3.2 cs408 multisource 树

命令：

```text
py -3.12 tools/verify_tree.py data/structured_materials/cs408/knowledge_tree_multisource.yaml
```

实际结果：退出码 0；`contract: OK (410 nodes)`；`tree shape: cs408`；`structure: {'subject': 20, 'chapter': 24, 'section': 116, 'item': 250}`；`ALL CHECKS PASSED`。

### 3.3 math1 树

命令：

```text
py -3.12 tools/verify_tree.py data/structured_materials/math1/knowledge_tree.yaml
```

实际结果：退出码 0；`contract: OK (69 nodes)`；`tree shape: math1`；`structure: {'subject': 3, 'chapter': 22, 'section': 44}`；`ALL CHECKS PASSED`。

### 3.4 eng1 树

命令：

```text
py -3.12 tools/verify_tree.py data/structured_materials/eng1/knowledge_tree.yaml
```

实际结果：退出码 0；`contract: OK (24 nodes)`；`tree shape: structure`；`structure: {'section': 13, 'item': 11}`；`ALL CHECKS PASSED`。

### 3.5 全量 unittest

命令：

```text
py -3.12 -m unittest discover -s tests -q
```

实际输出：

```text
----------------------------------------------------------------------
Ran 248 tests in 104.027s

OK
```

## 4. 四条变异测试与还原哈希

四条测试都只把 YAML 副本写入系统临时文件；测试内部实际启动 `verify_tree.py`，断言退出码非零并断言对应错误消息。外层 unittest 的 `OK` 表示“变异验证器按预期变红且还原哈希断言为绿”，不是变异树通过验证。

| 变异 | 独立命令 | 内层验证器结果 | 外层测试 | 真实文件变异前 SHA-256 | 真实文件变异后 SHA-256 | 还原 |
|---|---|---|---|---|---|---|
| a. 删除 cs408 一个 section 的章前缀节点 | `py -3.12 -m unittest tests.test_verify_tree_shapes.VerifierMutationTest.test_cs408_missing_chapter_prefix_is_rejected -v` | 红；非零，命中 `section has no direct chapter-NN ancestor` | `Ran 1 test ... OK` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | 绿，`RESTORED=True` |
| b. 删除 math1 某章 `.content` | `py -3.12 -m unittest tests.test_verify_tree_shapes.VerifierMutationTest.test_math1_missing_content_is_rejected -v` | 红；非零，命中 `missing <base>.content` | `Ran 1 test ... OK` | `a6657d2c6f64da6b91fcf0ae5e97c625fa15055d9bf2d87efc5901b6c73845b5` | `a6657d2c6f64da6b91fcf0ae5e97c625fa15055d9bf2d87efc5901b6c73845b5` | 绿，`RESTORED=True` |
| c. 在 cs408 section 下加入 `scope=subject` 真子节点 | `py -3.12 -m unittest tests.test_verify_tree_shapes.VerifierMutationTest.test_subject_scope_node_below_cs408_section_is_rejected -v` | 红；非零，命中 `must be narrower than chapter` | `Ran 1 test ... OK` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | 绿，`RESTORED=True` |
| d. 同时加入 cs408 与 math1 chapter 标记 | `py -3.12 -m unittest tests.test_verify_tree_shapes.VerifierMutationTest.test_ambiguous_cs408_and_math1_markers_are_rejected -v` | 红；非零，命中 `ambiguous chapter tree` | `Ran 1 test ... OK` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | 绿，`RESTORED=True` |

聚焦回归命令：

```text
py -3.12 -m unittest tests.test_verify_tree_shapes tests.test_round29_tree_split -v
```

实际输出摘要：`Ran 22 tests in 22.406s`，`OK`。

## 5. 开工前与结束后的测试基线

| 时点 | 命令 | 实际结果 |
|---|---|---|
| 开工前 | `py -3.12 -m unittest discover -s tests -q` | `Ran 238 tests in 101.307s`，`OK` |
| 结束后 | `py -3.12 -m unittest discover -s tests -q` | `Ran 248 tests in 104.027s`，`OK` |

净增 10 个聚焦测试。原有 round-29 测试从“两个 cs408 文件以同样方式失败”改为“两个文件都必须以退出码 0 完整通过”，避免相同失败被误当成回归保护。

## 6. 改动文件及 SHA-256

| 文件 | 改动前 SHA-256 | 改动后 SHA-256 | 说明 |
|---|---|---|---|
| `tools/verify_tree.py` | `604e48907794e3edd8a8924c0dec17940e934db062a8d9a292fb719ba947ae69` | `a3fa06f96fe5670ec146db3414ff3ac4a37ebdf0268c405f1b7e3c1896259c3a` | 三树形识别、分支祖先规则、subject 规则 |
| `tests/test_round29_tree_split.py` | `8a732e8a0fc3ec55ae25b69ed5f86139bff983b0fdfe3c218932061a73aba76f` | `2dad6498d9d62c8304ec0440e93a885d2c6cefabe3f27e1e5da221048bb03e2f` | 移除过时的“同样失败”契约，要求完整通过 |
| `tests/test_verify_tree_shapes.py` | 不存在 | `df5874a587eb825ae7e45c8929625bf4ec80ec2b98fbf5a9a59707f498fdd071` | 新增 10 个树形、subject、变异测试 |

本报告 `review/rounds/round-31-verifier-fix-codex.md` 写入前不存在。最终自身 SHA-256 无法可靠嵌入自身正文：加入哈希值会再次改变文件字节；交付完成后可由外部命令计算。这里不伪造一个“最终自身哈希”。

### 禁改文件复核

以下开工前与结束后 SHA-256 完全一致：

| 文件 | SHA-256 |
|---|---|
| `data/structured_materials/cs408/knowledge_tree.yaml` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` |
| `data/structured_materials/cs408/knowledge_tree_multisource.yaml` | `d9d3238ee9722b46e4d89188bb84d4d9f54f83bdefdd385a635694fc268b74a1` |
| `data/structured_materials/math1/knowledge_tree.yaml` | `a6657d2c6f64da6b91fcf0ae5e97c625fa15055d9bf2d87efc5901b6c73845b5` |
| `data/structured_materials/eng1/knowledge_tree.yaml` | `65e2aa730fd02b2e400bd95bd90361bc840187bf36029f6bbcd582e9d0156129` |
| `ky/knowledge/knowledge_point.py` | `46f22979a20dfc5fd9053a1cc665ac5b4e8721c8fefda6f7b67a04e03d921292` |

未执行 Git 命令。

## 7. 我实测到了 vs 我推断

### 我实测到了

- 四棵指定真实树均为退出码 0 且打印 `ALL CHECKS PASSED`。
- 开工前 238 个测试通过，结束后 248 个测试通过。
- 四条变异均由验证器非零退出并命中指定错误片段；对应真实数据文件前后哈希一致。
- 两个 cs408 文件分别被识别为 403/410 节点的 `cs408` 树形；math1 为 `math1`；eng1 为 `structure`。
- 指定四棵数据树及 `knowledge_point.py` 的开工前、结束后哈希一致。

### 我推断

- 用独立正标记再检查完整 chapter id 集合，比先后尝试分支更能满足“不明即拒”；依据是混合标记变异确实被拒绝。
- `chapter-NN`/`section-NN` 的两位数字正则是对任务书 `NN` 的严格解释，而不是从所有未来数据格式中证明出的永久规则。
- 当前 subject 同层语义需要 scope 与父前缀/直接父关系联合判断；仅凭字符串 `startswith` 无法表达其层级。

## 8. 没有把握的地方

1. 如果未来合法 cs408 编号超过两位或改为一位，当前严格正则会按设计拒绝；届时应明确迁移规则，不能自动放宽。
2. 当前数据允许 `scope=subject` 的语义同层节点使用不同 id 深度；本轮按“直接父前缀”区分真子节点。若未来出现更复杂的 subject 嵌套，需要显式父关系字段或更完整的 schema，不能只靠 id 猜测。
3. 变异 c 在 cs408 中由 chapter 整棵子树的 rank 检查直接挡住；这证明本轮指定场景，但不能外推为“无 chapter 的任意 structure 树也会拒绝相同变异”。任务书未要求把 structure 树改造成通用 scope DAG 验证器。
4. 本轮对禁止改动的四棵指定树和 `knowledge_point.py` 有前后哈希证据；没有在开工前保存整个 `data/**` 的全目录哈希清单，因此不声称拥有全目录级的前后哈希证明，只能确认执行过程中未对其他 data 路径实施写操作。
