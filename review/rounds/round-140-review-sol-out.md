# Round 140 Codex 复审：WP-G2b 与 WP-G3b

## 方法与范围

分别以 `git archive` 展开 `2d585ff`、`9cfd943`，另展开 `2d585ff^` 作索引脚本旧位置对照。三份副本均在系统临时目录；原始资料从我第 139 轮保留的临时副本复制（47 个文件，73,005,384 字节），并按注册表建立产品空目录。只通过 `GIT_DIR` 读取固定 Git 对象；没有读取或改动当前主仓库工作区。没有跑全量测试。

## 一、WP-G2b（`2d585ff`）：**FAIL**

### 必须改

**G2b-M3：README 把分类器产物写成可接入 M6 聚合的编码批次。** `tools/README.md` 步骤 3 写“Classify one paper into a batch file”，随后紧接“Aggregate the registered batches”。在归档中把占位符换成已登记的 2024 年 408 PDF，执行：

```text
py -3.12 tools/classify_questions.py --pdf data/raw_materials/cs408/past_papers_thirdparty/408_2024_paper_rebuild.pdf --year 2024 --out cache/review140/classification_batch.json --workspace kaoyan.workspace.yaml
```

命令 exit 0，写出 47 道题；JSON 顶层是 `year/paper/questions/confidence_counts/method/rows`，没有 `meta`、`entries`。`contracts/topic_weights.md` §“Coder entries and validation”要求每个编码员输出含 `meta` 和 `entries`。在内存中把该 JSON 替代一个已登记 coder 输出，再调用 `aggregate_topic_weights`，实际得到 `ContractError: ...map-cs408-2023-sol.json.meta: expected a mapping`。因此该命令只产生题目到小节的候选映射，不能直接产生可登记的 M6 编码批次；正常用户按步骤 3 为新卷准备权重会卡住。请把它标为辅助候选/人工编码输入，说明受审编码员输出与批次 manifest 的必要步骤及目前是否有生成入口，不要称其本身为可聚合批次。

**G2b-M4：归档索引的 provenance 与年份说明有可核实的错项。** `tools/README.md` 两条新归档清单行称登记索引带后加的 `paper_source`；在归档执行 `rg -l 'paper_source' data/exam_questions -g '*_index_*.json'` 无命中，逐份解析 11 个登记索引也未发现该字段。它们确有后加的 `knowledge_point_weights`，足以说明生成器不能逐字节重现；请删除不实的 `paper_source` 理由。清单和限制段把 `build_exam_indexes.py` 的 Math I / English I 范围合写为 2023–2026；实际 `py -3.12 tools/archive/build_exam_indexes.py --subject eng1 --year 2023` 报 `eng1 starts at 2024 in the registered source set`。请分开注明 Math I 2023–2026、English I 2024–2026。位置：`tools/README.md` 的两条索引归档清单行及“Current gaps and limits”。

### 建议改

本轮无额外建议项。

### 不改：上一轮问题与迁移验证

| 项 | 可复现输入与结果 |
| --- | --- |
| 第 135 轮 M1：步骤 2 / 3 / 5 的命令可执行 | 步骤 2 的 `verify_tree.py data/structured_materials/math1/knowledge_tree.yaml --workspace kaoyan.workspace.yaml` exit 0、69 节点和来源校验通过；`verify_408_index.py --workspace kaoyan.workspace.yaml` exit 0、11 个登记索引通过。步骤 3 的上述分类命令 exit 0，`aggregate_topic_weights.py --check` exit 0，`apply_knowledge_weights.py --check` exit 0、`write=0`。步骤 5 的 `extract_cs408_bundle.py --workspace kaoyan.workspace.yaml` exit 0、410 节点/188 题，`build_408_deck_scaffold.py --workspace kaoyan.workspace.yaml` exit 0、写出 116 个临时副本中的讲解壳文件。步骤 3 的产物语义问题见 G2b-M3。 |
| 第 135 轮 M2：408 v2 年份 | 归档脚本 `--help` 列出 `{2023,2024,2025,2026}`，`--year 2027` 被 argparse 拒绝；README 已将 408 v2 改为 2023–2026。这项已解决。 |
| 两个索引脚本搬迁、产物与写入边界 | `git diff --find-renames=30% --unified=1 2d585ff^ 2d585ff` 显示 v2 只改自身用法文字及仓库根 `parents[1]→[2]`，Math I / English I 构建器只改根路径。旧新两份归档以相同原始资料运行：v2 的 2023–2026 四份 `--out` 产物逐字节相同，均不同于对应登记索引；Math I 2024、English I 2024 默认写入产物在旧新位置逐字节相同，均不同于登记索引，测试后恢复临时副本原文件。v2 从新位置的 `--out` 仍可写临时目标；Math I / English I 脚本仍无 `--out`。README 明警告 v2 必须指定仓库外 `--out`、另一脚本不得在真实仓库运行；步骤 2 已改为验证登记索引。归档取舍合理。 |
| 清单与只读状态 | `py -3.12 -m unittest tests.test_tools_catalog tests.test_migrate_vocab_delivery tests.test_exam_index` → **12 项 OK**。README 清单与脚本目录双向一致。复核结束后，11 个登记索引和 `topic_weights.json` 的副本字节均等于 `git show 2d585ff:<路径>`；只读命令未改变它们。 |

## 二、WP-G3b（`9cfd943`）：**FAIL**

### 必须改

**G3b-M1 部分解决：新增组合仍漏掉实际可交换的相邻校验段。** `tests/contract/test_models_split_baseline.py` 新增 7 段配置错误的 21 对组合和 8 段复习项错误的 28 对组合；但配置列表没有“科目 ID 唯一性”和“至少一个活跃科目”，复习项列表没有最后的“词汇批次分钟上限”。因此以下两个相邻段顺序回归仍会让对照测试保持绿色：

1. 配置输入：从 `config-minimal.yaml` 复制，所有 subject 设 `active=False, weight=0.0, min_daily_minutes=0`，再令第二个 `subject_id` 等于第一个。提交版先报 `subjects[1].subject_id: duplicate subject_id`。在临时副本仅交换 `_check_unique_subject_ids(subjects)` 与 `active = _active_subjects(subjects)` 两行，首报变为 `subjects`，但 `py -3.12 -m unittest tests.contract.test_models_split_baseline` 仍 **1 项 OK**。
2. 复习项输入：从 `reviews-normal.yaml` 首项复制，设 `granularity='vocabulary_batch'`、`estimated_minutes=6`、`last_quality=6`。提交版先报 `items[0].last_quality`；在临时副本仅交换 `_review_item_feedback` 与 `_check_vocabulary_minutes` 的调用次序，首报变为 `items[0].estimated_minutes`，同一对照测试仍 **1 项 OK**。

请为这两对加入明确的双错误变体；再逐个核对主函数中其他可独立交换的相邻校验段，而不只核对 `section_errors` 列表的相邻项。变体仍须与固定 `b97f3ac` 基线比较异常类型、完整消息、路径和预期失败。两个变异只在临时副本执行，源码已逐字节恢复。

### 建议改

本轮无额外建议项。

### 不改：第 139 轮指定修法

| 项 | 可复现输入与结果 |
| --- | --- |
| 两个原调换变异 | 在临时副本交换 `_config_self_rating_mode` 与 `_config_project_and_budget`，对照测试 exit 1，失败样本 `config-cross-policy-project`；交换 `_review_item_dates` 与 `_load_schedule`，exit 1，失败样本 `review-cross-dates-schedule`。第 139 轮的两处盲点已补。 |
| 固定基线、标签及根类型 | 基线仍取 `b97f3ac:ky/models.py`，断言旧 `validate_config` 长于 90 行。配置共 84 个变体（21 个跨段组合），复习项共 86 个（28 个跨段组合），变体名唯一；新增 `config-root-not-mapping` 与 `review-root-not-mapping` 并断言失败。新旧合法结果按 dataclass 全字段比较，非法结果按类型、完整消息、路径比较。辅助函数已改为 `_config_project_and_budget`、`_review_item_identity_and_title`，名称覆盖所解析的字段；实现逻辑未变。 |
| 定向验收 | `py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler tests.contract.test_models_split_baseline tests.contract.test_workspace_split_baseline` → **104 项 OK**。两项遗漏由额外变异发现，不是当前输入下已观察到的实现回归。 |

## 安全登记

本轮没有发现仅在恶意输入、内部文件篡改或精确并发交错时触发的新增安全问题。

## 门禁结论

- **WP-G2b FAIL**：上一轮两项的命令形式与 408 v2 年份已修；README 仍把分类候选图误称编码批次，并含可核实的索引 provenance / 科目年份错项。
- **WP-G3b FAIL**：原两项调换变异已变红，但“所有相邻段”的首报顺序还未被对照测试锁住。
