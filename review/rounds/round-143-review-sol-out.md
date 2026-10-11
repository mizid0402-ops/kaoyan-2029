# Round 143 复审：G2b README 与 G3b 对照测试

## 范围与方法

分别用 `git archive ad3b78a`、`git archive 95bbc1a` 展开到系统临时目录，补入上一轮临时副本保存的 47 份原始资料（73,005,384 字节）和产品空目录。所有命令、变异和产物均在各自归档内；固定基线通过指向主仓库对象库的 `GIT_DIR` 读取。评审输入均来自临时归档，主仓库工作区只写并复读本报告；没有跑全量测试。严重度按 `AGENTS.md` 的个人本机使用威胁模型判定。

## 一、G2b README（`ad3b78a`）：**PASS**

### 必须改

无。

### 建议改

**G2b-S1：将“每批三份编码员文档”写成依注册表数量。** `tools/README.md` 步骤 3 的 “A batch is three independent coder documents” 符合当前 `data/review_weights/batches.yaml` 的三名编码员，却像是永久的格式限制。`contracts/topic_weights.md` 规定的是每个已登记 coder 各有一份文档；`ky/exam/topic_weights.py` 从 manifest 读取非空 coder 列表并要求每批键集合与之相同，没有固定三人的限制。可复现输入：查看当前 manifest 的 `coders: [sol, luna, claude]`，再查看 `ky/exam/topic_weights.py` 中 `_load_manifest_settings` 对 `coders` 的非空校验及 `_read_entries` 的集合校验。建议改成“每个 manifest 登记的 coder 各一份（当前为三份）”。当前数据和操作不受影响，因此不阻断本包。

### 不改：第 140 轮 M3、M4 已解决

| 项 | 可复现输入与结果 |
| --- | --- |
| 分类器产物与编码批次 | 在 `ad3b78a` 归档运行 `py -3.12 tools/classify_questions.py --pdf data/raw_materials/cs408/past_papers_thirdparty/408_2024_paper_rebuild.pdf --year 2024 --out cache/review143/candidates.json --workspace kaoyan.workspace.yaml --show 1`，exit 0，产物顶层为 `year/paper/questions/confidence_counts/method/rows`，无 `meta`、`entries`。README 清单与步骤 3 均明确称其为候选映射、不能直接聚合；这与 `contracts/topic_weights.md` 的编码员文档格式一致。 |
| 编码员文档生成入口 | 在归档中检索 `tools/`、`ky/` 的 `coder_outputs`、`batches.yaml`，命中的是 `tools/aggregate_topic_weights.py` 的读取和 `ky/exam/topic_weights.py` 的校验；分类器的 `_write_result` 只写上述候选映射。未发现生产脚本写 `meta` + `entries` 编码员文档，README 的“由编码员编写、审核；没有脚本生成”与现有工具一致。 |
| 索引 provenance 与年份 | 解析 `data/exam_questions/*_index_*.json`：11 份均无顶层 `paper_source`，均有条目级 `knowledge_point_weights`。README 现仅以后者说明归档构建器无法重现登记索引。`tools/archive/build_exam_indexes.py` 的 `MATH` 键为 2023–2026，`ENG_PAPER` 只含 2024–2026；README 清单和限制段均已分别写明。 |
| 定向验证 | `py -3.12 -B -m unittest tests.test_tools_catalog`：1 项 OK，README 清单与实际脚本路径一致。 |

## 二、G3b 对照测试（`95bbc1a`）：**PASS**

### 必须改

无。

### 建议改

无。

### 不改：调换变异与变体构造已覆盖本轮问题

固定基线仍为 `b97f3ac:ky/models.py`。在归档中设置 `GIT_DIR=F:\workspace\kaoyan-ai-system\.git`、`PYTHONDONTWRITEBYTECODE=1`，运行 `py -3.12 -B -m unittest tests.contract.test_models_split_baseline`：1 项 OK。测试的子用例比较合法结果的 dataclass 全字段，以及非法结果的异常类型、完整消息和路径；还断言每个变体标注的成功或失败。

在临时归档逐次只交换 `ky/models.py` 中指定两段调用，每次运行同一测试并清除 `ky/__pycache__/models*.pyc`；以下四个第 139/140 轮调换变异全部 exit 1，且只在对应组合变体报错：

| 调换的相邻段 | 抓到回归的变体 |
| --- | --- |
| `_config_self_rating_mode` / `_config_project_and_budget` | `config-cross-policy-project` |
| `_review_item_dates` / `_load_schedule` | `review-cross-dates-schedule` |
| `_check_unique_subject_ids` / `_active_subjects` | `config-cross-unique-no-active` |
| `_review_item_feedback` / `_check_vocabulary_minutes` | `review-cross-feedback-vocabulary` |

`_with_value` 现仅对字典补缺失中间键，列表下标直接索引。用 `config-minimal.yaml` 生成变体后检查：`config-subject-id-type`、`config-display-name-type`、`config-cross-subject-weights`、`config-cross-unique-no-active` 的 `subjects` 仍是列表，首两个科目仍是保留其他字段的字典（首项五个键），没有被替换成 `{}`。`review-cross-feedback-vocabulary` 同时实际写入 `last_quality=6`、`granularity=vocabulary_batch`、`estimated_minutes=6`。生成的配置 104 个、复习项 93 个变体均在基线测试中通过预期成功/失败断言，且名字唯一。

按 `validate_config`、`validate_review_item` 的调用顺序检查，17 对相邻校验段中 15 对有跨段双错误变体。另两对因测试选用的错误编辑同一字段而被组合生成器跳过；直接调换并重跑仍会变红：将“至少一个活跃科目”置于“活跃权重求和”之后，`config-no-active-subject` 失败；将 `_check_floor_room` 置于 `_check_subject_minimums` 之前，`config-subject-minutes-exceeds-total` 失败。后者输入是首个科目的 `min_daily_minutes=total_daily_minutes+1`；前者输入是所有科目 inactive、权重和最低分钟均为零。两处顺序因此也被现有单错误变体锁住。每次变异后源码恢复；通过 Python 读取 Git 对象与临时文件的原始字节，二者 SHA-256 均为 `47e5fbf294a25b1d2f0e3cec941174449724666d84c3d427c97cf53e6bba1c`。

## 安全登记

本轮未发现需单独登记的新增安全问题。

## 结论

- **G2b PASS**：第 140 轮 M3、M4 已解决；固定“三份”的文字建议随下次文档编辑调整。
- **G3b PASS**：四个旧调换变异均变红，列表下标变体按意图构造；其余相邻段的两处组合跳过仍由单错误变体检出。
