# Round 33：`verify_tree.py` 树形静默降级加固报告（Codex）

日期：2026-09-15  
实现范围：`tools/verify_tree.py`、`tests/test_verify_tree_shapes.py`；本文件为指定报告。  
结论：**PASS**。F1–F5 已实现，9 条完成标准全部满足。

## 1. 实现结果

### F1：命名空间承重路由

- 新增 `SUPPORTED_ROOT_SHAPES = {"cs408": "cs408", "math1": "math1", "eng1": "eng1"}`。
- `infer_tree_shape(points)` 现在从**全部节点 ID**提取首段命名空间，要求恰好一个根且必须已注册。
- `scope` 不再参与 profile 路由；不存在“无章标记就回退 structure”的分支。
- eng1 是显式 `eng1` profile，不再是剩余情况的默认值。

### F2：profile 内 ID 语法校验

- cs408 章仍完整匹配 `<subject>.<domain>.chapter-NN`；section 仍完整匹配 `<...>.chapter-NN.section-NN`，并沿用 round-31 的直接父章检查。
- math1 章完整匹配 `<...>.chapter`；每章仍要求同级 `.content` 与 `.requirements`，并补强为两者必须是 `scope=section`。
- 未删除任何既有 source hash、quote_ref、父节点、subject、frequency/evidence 或 require-scopes 检查。

### F3：章 ID/scope 双向双条件

新增 `chapter_scope_failures(points, tree_shape)`，对 cs408、math1 执行双向约束；eng1 无合法章语法，因此任何 `scope=chapter` 都失败：

1. ID 匹配本 profile 章语法但 `scope != "chapter"`：
   `id matches chapter pattern but scope={scope!r}`。
2. `scope == "chapter"` 但 ID 不匹配本 profile 章语法：
   `scope='chapter' but id does not match <profile> chapter pattern`。

单元测试分别覆盖 cs408、math1 的两个方向，以及 eng1 的反向拒绝。

### F4：不明即拒

- 混合命名空间：`TreeShapeError: mixed knowledge-point namespaces`。
- 未登记命名空间：`TreeShapeError: unsupported knowledge-point namespace`。
- 同一命名空间内同时出现 cs408 `chapter-NN` 与 math1 `.chapter` 语法：`TreeShapeError: ambiguous id syntax`。
- 命名空间 profile 与单一外来语法标记冲突：`TreeShapeError: ... conflicts with <profile> id syntax`。
- 上述情况均无宽松分支或默认放行。

### F5：保留 round-31 适配

- cs408 section 仍以去掉最后一段后的 `chapter-NN` ID 作为直接父章，没有恢复错误的 `.chapter` 后缀假设。
- math1 仍使用同级 `<base>.chapter` 祖先模型。
- subject 同父语义 peer 规则与真实层级违规检查均保留。
- 四棵真实树均通过，单删一个 cs408 章与 round-31 的其他变异仍变红。

## 2. 九条完成标准逐条证据

### 1. 四棵真实树 exit=0

| 树 | 节点数 | profile | 结果 |
|---|---:|---|---|
| `data/structured_materials/cs408/knowledge_tree.yaml` | 403 | cs408 | exit=0，`ALL CHECKS PASSED` |
| `data/structured_materials/cs408/knowledge_tree_multisource.yaml` | 410 | cs408 | exit=0，`ALL CHECKS PASSED` |
| `data/structured_materials/math1/knowledge_tree.yaml` | 69 | math1 | exit=0，`ALL CHECKS PASSED` |
| `data/structured_materials/eng1/knowledge_tree.yaml` | 24 | eng1 | exit=0，`ALL CHECKS PASSED` |

四条命令均为 `py -3.12 tools/verify_tree.py <tree>`，且 contract、hashes、quote_ref、structure 全部通过。

### 2. 全量 unittest 全绿

```text
py -3.12 -m unittest discover -s tests -q
----------------------------------------------------------------------
Ran 261 tests in 110.578s

OK
exit=0
```

定向最小范围验证：

```text
py -3.12 -m unittest tests.test_verify_tree_shapes -q
----------------------------------------------------------------------
Ran 23 tests in 12.586s

OK
exit=0
```

261 项全套通过后，仅将验证器模块文档字符串中的 `immutable id namespace`
纠正为更准确的 `registered id namespace`，没有修改可执行逻辑。按“最小范围有效即不重复全量”
的测试纪律，随后只重跑上述 23 项定向测试与 `py_compile`，二者均 exit=0。

### 3. 删除全部章节点变红

- cs408：`test_cs408_all_chapters_deleted_is_rejected`，退出码非零，命中 `section has no direct chapter-NN ancestor`。
- 对称加固：`test_math1_all_chapters_deleted_is_rejected`，退出码非零，命中 `section has no ancestor node`。

### 4. 章 scope 改标为 section 变红

`test_cs408_chapter_scopes_relabelled_is_rejected` 将全部 24 个章改标为 section；退出码非零，命中：

```text
id matches chapter pattern but scope='section'
```

### 5. 单删一个章仍变红

`test_cs408_missing_chapter_prefix_is_rejected` 删除一个真实章；退出码非零，命中 `section has no direct chapter-NN ancestor`。round-31 行为未回退。

### 6. 混合命名空间变红

`test_mixed_namespace_is_rejected` 将一个 cs408 节点的首段改为 math1；退出码非零，命中 `mixed knowledge-point namespaces`。

### 7. 未知命名空间变红

`test_unknown_namespace_is_rejected` 将全部 cs408 ID 首段改为 unknown；退出码非零，命中 `unsupported knowledge-point namespace`，没有默认放行。

### 8. 每条变异测试的还原哈希

所有变异均在系统临时 YAML 副本执行：先复制原字节，写入变异，实际调用验证器，最后在 `finally` 中恢复原字节；测试断言 `mutated != before` 且 `restored == before`。每个测试的输出如下：

| 变异测试 | before SHA-256 | mutated SHA-256 | restored SHA-256 | 还原 |
|---|---|---|---|---|
| `test_cs408_all_chapters_deleted_is_rejected` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | `31074d4845c67001f4ada1433040640af151f4336c9b1ebec9fcd9da74536fbb` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | 相等 |
| `test_cs408_chapter_scopes_relabelled_is_rejected` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | `202b9078619947aa4cf89f57d179c11b9d0592ddcf7499c352c24135abf736bf` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | 相等 |
| `test_cs408_missing_chapter_prefix_is_rejected` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | `aae6f9fac6be3837ceabb82c815b2238819ffd49e468c4b55a667bd1877bf075` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | 相等 |
| `test_mixed_namespace_is_rejected` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | `0fe5167d854a07a96b3ae729c14e4f1620bff96ec4bce4b3103f74ba264c3e3a` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | 相等 |
| `test_unknown_namespace_is_rejected` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | `62213d1f43ce4f07274fc6af56871c47466d56d0327af9209f25521495053d7c` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | 相等 |
| `test_ambiguous_cs408_and_math1_markers_are_rejected` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | `3e88d9531e8edece321566dc1b61bd1a884775f14bf0c86d4f0ecedcf7c05aa5` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | 相等 |
| `test_subject_scope_node_below_cs408_section_is_rejected` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | `62ae35a567e4cfb55eb7c2d716e139df924e3d5015ba8179a742edd0b834ba5b` | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` | 相等 |
| `test_math1_all_chapters_deleted_is_rejected` | `a6657d2c6f64da6b91fcf0ae5e97c625fa15055d9bf2d87efc5901b6c73845b5` | `521a2c8fcd4844c19af1c80d3c0855e52bcf67322cb8c0ee1064a475dca433a3` | `a6657d2c6f64da6b91fcf0ae5e97c625fa15055d9bf2d87efc5901b6c73845b5` | 相等 |
| `test_math1_missing_content_is_rejected` | `a6657d2c6f64da6b91fcf0ae5e97c625fa15055d9bf2d87efc5901b6c73845b5` | `0bd44a59a98d4b9479df2b7748f9836e654333f2072ee9c49c8af28b20c5f061` | `a6657d2c6f64da6b91fcf0ae5e97c625fa15055d9bf2d87efc5901b6c73845b5` | 相等 |
| `test_math1_required_content_wrong_scope_is_rejected` | `a6657d2c6f64da6b91fcf0ae5e97c625fa15055d9bf2d87efc5901b6c73845b5` | `d3a984829c656f2333d41efc349486d1928a413acff2ec81e59fbe959279c8b4` | `a6657d2c6f64da6b91fcf0ae5e97c625fa15055d9bf2d87efc5901b6c73845b5` | 相等 |

此外，每个变异测试 `tearDown` 都重新哈希四棵受保护真实树并与 `setUp` 值逐一相等；真实数据文件从未作为写入目标。

### 9. `data/**` 零字节改动

按相对路径排序，对 `data/**` 每个文件计算 SHA-256，再对完整清单计算 SHA-256：

| 时点 | 文件数 | 清单 SHA-256 |
|---|---:|---|
| 实现前 | 141 | `daf32fd4edce68eee959edbe9d5ee7ca4d614879b0d464fc896313074c84ac4e` |
| 实现后 | 141 | `daf32fd4edce68eee959edbe9d5ee7ca4d614879b0d464fc896313074c84ac4e` |

四棵真实树的前后单文件 SHA-256 也分别保持：

| 文件 | SHA-256 |
|---|---|
| cs408 基线 | `a535394dafe21681c974f3114c3a20cdcc090403ca4b05665903dcbf48008418` |
| cs408 主表 | `d9d3238ee9722b46e4d89188bb84d4d9f54f83bdefdd385a635694fc268b74a1` |
| math1 | `a6657d2c6f64da6b91fcf0ae5e97c625fa15055d9bf2d87efc5901b6c73845b5` |
| eng1 | `65e2aa730fd02b2e400bd95bd90361bc840187bf36029f6bbcd582e9d0156129` |

## 3. 禁改边界与文件哈希

`ky/knowledge/knowledge_point.py` 未改，前后 SHA-256 均为：

```text
46f22979a20dfc5fd9053a1cc665ac5b4e8721c8fefda6f7b67a04e03d921292
```

实现文件前后哈希：

| 文件 | 实现前 SHA-256 | 实现后 SHA-256 |
|---|---|---|
| `tools/verify_tree.py` | `a3fa06f96fe5670ec146db3414ff3ac4a37ebdf0268c405f1b7e3c1896259c3a` | `fac5f12fdfde4a45e05be6029cc1f42cd5c8bcc5f9c97d2e075b565e4e6266cd` |
| `tests/test_verify_tree_shapes.py` | `df5874a587eb825ae7e45c8929625bf4ec80ec2b98fbf5a9a59707f498fdd071` | `4491a50510abba32c14bcf4d68f54d8c177fe516f5697086d64a4577ff3188b2` |

本目录没有可用的 Git 元数据（`git status` 返回 `not a git repository`），因此没有用 Git diff 冒充范围证明；以上证据来自本轮开始和结束时的实际字节哈希，以及本轮 `apply_patch` 的明确目标记录。

## 4. 最终审查门

- 原缺陷：**RESOLVED**。删光章或改标章 scope 均不能再关闭 profile 检查。
- F1/F3 组合：**RESOLVED**。命名空间负责路由，章 ID/scope 双向一致性负责防改标。
- F4 未知/混合/歧义：**RESOLVED**，全部非零退出。
- round-31 直接父章回归：**无回退**。
- fix-induced BLOCKER/MAJOR：**None**。
- `py -3.12 -m py_compile tools/verify_tree.py tests/test_verify_tree_shapes.py`：exit=0。
- Gate：**PASS**。
