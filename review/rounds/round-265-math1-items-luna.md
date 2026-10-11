# 第 265 轮：数学一考试要求条目拆分（luna）

## 改动

- 数学一知识树从 69 增至 192 个节点；新增 123 个 `scope: item`，父节点为对应 `requirements` 小节。节点均为 `extracted`，未推进状态。
- `named_chapters` 语法接受 `requirements.item-NN`，拒绝父小节缺失、挂在 `content` 下或 ID/scope 不符的 item。验证器的 scope 统计自动包含 item。
- 更新数据清单计数、知识树结构说明和旁置报告。未改其他项目窗口文件；未提交。
- 原构建器 `tools/build_math1_tree.py` 未在本轮允许修改范围内，仍只生成旧 69 节点骨架；树注释与旁置报告已标注不可用它覆盖本轮更新。

## 每章条目数

| 章 | 条目 | 章 | 条目 | 章 | 条目 |
|---|---:|---|---:|---|---:|
| 高数 1 | 10 | 高数 2 | 9 | 高数 3 | 6 |
| 高数 4 | 9 | 高数 5 | 9 | 高数 6 | 8 |
| 高数 7 | 11 | 高数 8 | 9 | 线代 1 | 2 |
| 线代 2 | 5 | 线代 3 | 8 | 线代 4 | 5 |
| 线代 5 | 3 | 线代 6 | 3 | 概率 1 | 3 |
| 概率 2 | 5 | 概率 3 | 4 | 概率 4 | 2 |
| 概率 5 | 3 | 概率 6 | 3 | 概率 7 | 4 |
| 概率 8 | 2 | 合计 | 123 |  |  |

2022 与 2026 两份转录按编号逐章均为 123 条。2022 线代第 4 章首项原编号呈小写 `l.`，按第 258 轮报告确认的排版识别为第 1 条。旧构建报告 121/120 为排版计数；第 258 轮已复核为 123/123。

## 修正与差异

已确认转录错字修正，标题以 2022 转录与第 258 轮报告为依据：

- 高数第 7 章 item-07、item-08：2026 `幕级数` → `幂级数`。
- 概率第 3 章 item-04：2026 `稠` → `随机`。
- 概率第 5 章 item-02：2026 `伯努利大数定` → `伯努利大数定律`。
- 概率第 7 章 item-03：2026 `柑合性` → `相合性`。

已确认考试要求变更：概率第 1 章 item-03 保留 2026 的「概率计算的方法」；第 258 轮报告确认 2025 起增加「的方法」。

其余两源措辞、标点或转录内容差异共 25 条，均按任务书保留 2026 写法；没有据此判断官方内容变更。各条短定位及逐源 `quote_ref` 见 `data/structured_materials/math1/knowledge_tree_report.md`。

## 验收输出

`py -3.12 tools/verify_tree.py data/structured_materials/math1/knowledge_tree.yaml --workspace kaoyan.workspace.yaml`（退出 0）：

```text
contract        : OK (192 nodes validated by ky.knowledge.knowledge_point)
sources         : 2 distinct files, 2 hashed
hashes          : OK (every sources[i].sha256 matches the bytes on disk)
quote_ref       : OK (every quote_ref locates in its declared source)
tree shape      : math1
structure       : {'subject': 3, 'chapter': 22, 'section': 44, 'item': 123}

ALL CHECKS PASSED
```

`py -3.12 tools/aggregate_topic_weights.py --check`（退出 0），输出原文：

```text
topic_weights.json matches registered batches (numeric equality, no tolerance; 0.0 == -0.0)
```

`py -3.12 -m unittest tests.contract.test_knowledge_tree_port tests.test_data_manifest tests.test_verify_tree_shapes tests.test_tree_integrity tests.contract.test_topic_weights_port`（退出 0）：

```text
......................................................................
----------------------------------------------------------------------
Ran 70 tests in 25.887s

OK
MUTATION HASH test_ambiguous_cs408_and_math1_markers_are_rejected: before=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e mutated=3e88d9531e8edece321566dc1b61bd1a884775f14bf0c86d4f0ecedcf7c05aa5 restored=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e
MUTATION HASH test_cs408_all_chapters_deleted_is_rejected: before=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e mutated=31074d4845c67001f4ada1433040640af151f4336c9b1ebec9fcd9da74536fbb restored=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e
MUTATION HASH test_cs408_chapter_scopes_relabelled_is_rejected: before=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e mutated=202b9078619947aa4cf89f57d179c11b9d0592ddcf7499c352c24135abf736bf restored=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e
MUTATION HASH test_cs408_missing_chapter_prefix_is_rejected: before=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e mutated=aae6f9fac6be3837ceabb82c815b2238819ffd49e468c4b55a667bd1877bf075 restored=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e
MUTATION HASH test_math1_all_chapters_deleted_is_rejected: before=7ca8cf5a357402ef85568e8f7b0e734a8e994898c099c9f15aac31a1127400f4 mutated=9f0bd2dc58465f9dd89dbae631a3fd38b9e3ae0091da9c80e27204f60be65aeb restored=7ca8cf5a357402ef85568e8f7b0e734a8e994898c099c9f15aac31a1127400f4
MUTATION HASH test_math1_missing_content_is_rejected: before=7ca8cf5a357402ef85568e8f7b0e734a8e994898c099c9f15aac31a1127400f4 mutated=f8fddef29f4d18a4bf864293a20fdf6e510565c3ff2b64efd56f750f1b76be1e restored=7ca8cf5a357402ef85568e8f7b0e734a8e994898c099c9f15aac31a1127400f4
MUTATION HASH test_math1_required_content_wrong_scope_is_rejected: before=7ca8cf5a357402ef85568e8f7b0e734a8e994898c099c9f15aac31a1127400f4 mutated=34e166de74a380da9a9b3a72468fae06506031617cf7dbbe8d81ceeda664df43 restored=7ca8cf5a357402ef85568e8f7b0e734a8e994898c099c9f15aac31a1127400f4
MUTATION HASH test_mixed_namespace_is_rejected: before=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e mutated=0fe5167d854a07a96b3ae729c14e4f1620bff96ec4bce4b3103f74ba264c3e3a restored=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e
MUTATION HASH test_subject_scope_node_below_cs408_section_is_rejected: before=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e mutated=62ae35a567e4cfb55eb7c2d716e139df924e3d5015ba8179a742edd0b834ba5b restored=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e
MUTATION HASH test_unknown_namespace_is_rejected: before=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e mutated=62213d1f43ce4f07274fc6af56871c47466d56d0327af9209f25521495053d7c restored=fc369b440e2d51383586373844e3edf2cc89729e170d3d2249c777c7bb7a9d4e
national.json: write=0 unchanged=0 missing=1 rejected=0 single_node=0 spread=0
   - missing from topic_weights.json: cs408-2023-01
school.json: write=1 unchanged=0 missing=0 rejected=0 single_node=1 spread=0

TOTAL write=1 unchanged=0 missing=1 rejected=0 single_node=1 spread=0
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

之后微调了真实数学一叶子断言，按 AGENTS.md 只重跑受影响模块 `tests.contract.test_knowledge_tree_port`（退出 0）：

```text
............
----------------------------------------------------------------------
Ran 12 tests in 2.113s

OK
```
