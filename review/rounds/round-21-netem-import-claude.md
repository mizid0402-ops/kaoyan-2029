# Round 21：NETEM 词表导入英语一，作为第二份独立来源 — 实现报告

执行者：Claude Sonnet 5（claude-sonnet-5）
日期：2026-09-14
任务书：`review/rounds/round-21-netem-import-task.md`

## 0. 一句话结论

SHA-256 自算一致（`6d71a301...b185f`）；重合率（NETEM→真题，词形级）**23.50%**（1299/5528）；
反向覆盖率（真题→不在NETEM，词形级）**59.10%**（1877/3176，lemma 校正后降到 35.77%）；
测试基线：开工前 193 全绿 → 结束时 198 全绿（新增 5 条，0 条回归）；
报告：`review/rounds/round-21-netem-import-claude.md`。

---

## 1. SHA-256 核验（我实测）

文件：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\ghsurvey\downloads\netem_full_list.json`

| 项 | 任务书给出 | 我自算 | 一致？ |
|---|---|---|---|
| 字节数 | 1,106,068 | 1,106,068 | ✅ |
| SHA-256 | `6d71a301321056291902bc4804e223c6926dca0d629a45076a6ca5adab185f62` | 同左 | ✅ |
| 顶层 key 数 | 1 | 1（`"5530考研词汇词频排序表"`） | ✅ |
| 条目数 | 5530 | 5530 | ✅ |
| 字段 | 序号/词频/单词/释义/其他拼写/分类/子分类 | 同左（7 字段） | ✅ |
| 大小写折叠后唯一词数 | 5528 | 5528 | ✅ |
| 含空格短语 | 6 条 | 6 条：`according to / air conditioning / ice cream / living room / ought to / owing to` | ✅ |

**我实测到的额外细节**（任务书未列出，属于我自己发现）：
- 5530→5528 的 2 处折叠碰撞是 `may`(rank 68) / `May`(rank 5425) 和 `march`(rank 1989) / `March`(rank 5421)——都是"普通词 vs 专有名词/月份名"的大小写歧义对。
- `分类` 字段无空值（5530/5530 全部有值）；`子分类` 有 3258 条为空（约 58.9%）。
- `其他拼写` 非空的有 154 条，例如 `centre/center`、`program/programme`、`behavior/behaviour` 这类英美拼写变体，但也混有 `conversation/converzation`、`course/corse`、`rise/rize`、`employee/employe` 这类看起来更像"常见拼写错误"而非规范变体的条目（README 提到该字段取自另一个 `spelling-variations` 数据集，未经我核实其甄别标准）。
- 原始文件中有 31 个词形自带大写字母（`I / April / Bible / Christmas / ...`），多为专有名词/月份/宗教词，与"大小写折叠"决策直接相关。

结论：**SHA-256、字节数、结构、字段、条目数、去重后唯一数，均与任务书描述完全一致，未发现任何不一致，无需停下。**

---

## 2. 释义字段的处理方式

- **读了，但只在内存中读取一次，从未写入任何项目内文件或本次会话之外的持久化产物。**
- `tools/import_netem_source.py` 里的流程是：读原始 JSON → 立刻 `strip_entries()` 剔除 `释义` 字段 → 把剩余 6 个字段（序号/词频/单词/其他拼写/分类/子分类）写成新的 `data/english_vocabulary/netem_wordlist_stripped.json`（这是之后所有构建/校验步骤的唯一输入，原始带释义的 JSON 之后不再被读取）。
- 数据库表 `source_entries` 的列里没有任何释义相关列；`tests/test_netem_source.py::test_no_gloss_text_stored_anywhere_in_source_entries` 用中文字符正则（`[一-鿿]`）扫描 `word_form_original`/`word_form_norm`/`other_spellings` 三列，断言里面不含任何中文字符（分类/子分类允许含中文，未做此项断言，因为这两列本身就是被任务书列为"可落盘"的结构信息）。
- `tests/test_netem_source.py::test_stripped_json_has_no_definition_field` 直接对 `netem_wordlist_stripped.json` 全文做字符串搜索，断言不含 `释义` 二字。
- **理由**：释义可能来自第三方词典（README 自述"人工校对""另引 little dict"），且本项目的交叉验证只需要"词形/词频/排序"，不需要中文释义，落盘无收益、有风险，因此彻底不落盘。

---

## 3. 交叉验证的三个数字（本次最重要产出，我实测）

数据来源：`words` 表（`is_stopword=0`，3176 个非停用词词形，来自三年真题）× `source_entries` 表（NETEM，5530 条，5528 唯一词形）。全部基于**大小写折叠后的词形**比较。

### 3.1 重合率（NETEM → 真题）
```
overlap_count = 1299
overlap_rate_over_netem = 1299 / 5528 = 23.50%
```
即 NETEM 5528 个词里，有 1299 个（23.5%）确实以完全相同的词形出现在三年真题的非停用词表里。

### 3.2 反向覆盖率（真题 → 不在 NETEM）
```
reverse_not_in_netem_count = 1877
reverse_not_in_netem_rate_over_exam = 1877 / 3176 = 59.10%
```
即真题词库里近六成的词形，在 NETEM 的 5530 条词表里找不到完全相同的字符串。

**⚠️ 这个数字不能直接读作"59% 超纲"**——我做了一层追加分析（非任务书要求的三个数字之一，但对解释这个数字必不可少）：`words` 表存的是**原始出现词形**（如 `actions`、`achieved`、`accessibility`），而 NETEM 是**词典条目/词根级**词表（如 `action`、`achieve`）。用 `words.lemma` 再比对一次：
```
recovered_by_lemma_count = 741   # 用 lemma 折叠后能在 NETEM 找到的
still_missing_after_lemma_count = 1136
still_missing_after_lemma_rate_over_exam = 1136 / 3176 = 35.77%
```
也就是说，59.10% 里有约 13.9 个百分点（741/3176）纯粹是"词形 vs 词根"的记账口径差异，不是真的没覆盖到；扣掉这部分，"真正在 NETEM 词根层面也找不到"的比例是 35.77%。
对这 1136 个词做了抽样分类（非穷举）：
- **撇号缩略/所有格伪影**：83 个，例如 `aren't / can't / arizona's / boston's / california's / actors' / child's`——其中缩略词（`aren't/can't`）和地名所有格（`arizona's/boston's/california's`）明显是分词/专有名词伪影，不是"该学的词"。
- **连字符碎片/复合词**：97 个，例如 `a-g / a-h / ai- / ai-generated / ai-powered / born-digital / carbon-negative`——`a-g/a-h/ai-` 这几个明显是枚举编号或断词伪影（清洗质量问题的线索）；`ai-generated/ai-powered/born-digital/carbon-negative` 则像是很新的复合词，NETEM 语料库（README 自述基于约 200 套四六级/考研/专四专八试卷）大概率没有覆盖到这类新造词。
- 其余约 956 个未逐一分类，抽样看到不少专有名词（`africa/african/aegean/albany/agrawal`）和低频学术词（`accessibility/alloparenting/acuity`）。

**顺带验证清洗质量**：`a-g`、`a-h`、`ai-` 这类残片确认了三年真题词库构建时确实残留了少量分词伪影（此前 `words` 表构建报告里应该也提到过类似问题）；这算是本轮交叉验证意外验证到的一个既有清洗瑕疵的证据，但样本很小（3 个），不足以说明系统性问题。

### 3.3 按 NETEM 词频分层的重合率
```
top500_overlap_rate  = 300/500  = 60.00%
top1000_overlap_rate = 566/1000 = 56.60%
top2000_overlap_rate = 914/2000 = 45.70%
```
（均按 NETEM 内部 `rank` 升序取前 N 个去重词形，再与真题非停用词词形取交集，同样是词形级、非 lemma 级。）

**趋势解读（我的推断，非实测）**：NETEM 排名越靠前的词越"基础"（`the/be/have/...`），这些词本身就是常见功能词/系动词，出现在真题里往往就是原形，所以词形级重合率最高；越往后排的词更可能在具体真题句子里以屈折形式出现（复数、时态、派生），词形级重合率因此逐层下降。top2000 到全表（5528）重合率从 45.7% 降到 23.5%，说明尾部词（rank 2000–5530）里有相当一部分根本没在三年真题里以任何形式出现过——这与"三年真题只是完整大纲词表的一个小样本"这一预期是吻合的。

---

## 4. 与英语一现有来源的关系判断

现有登记来源 `eng1-outline-toc-aus-zxhsd-2026`（`data/materials.yaml:653`）：
- `material_kind: official_syllabus`，但 `rights.may_be_structured: false`，且我读取其 `notes`/字段可确认它只是**2026 版官方教材体系商品页公布的目录层级**（章节/考试范围结构），**不含词汇附录、不含任何词表**。

NETEM（本轮导入）：
- 是**词表**（5530 个具体词条 + 词频排序 + 分类），**不含考纲结构信息**（没有"完形填空占几分""阅读理解几篇"这类目录信息）。
- 其 README 自述锚定的是"**2024年**全国硕士研究生招生考试英语（一）考试大纲词汇表"要求掌握的 5530 词，**不是 2026 版**。

**判断：这两份来源覆盖的是完全不同的两个层次（考纲结构 vs 词汇清单），字段不重叠、粒度不重叠，不构成同源转载或重复计数。**

- `eng1-outline-toc-aus-zxhsd-2026` 能支撑的结论：2026 年英语一考试的**结构性**信息（如果其目录包含考试各部分的分值/篇幅），**不能**支撑任何"哪些词该背"的结论（它压根没有词表）。
- NETEM 能支撑的结论：**词汇范围与优先级**——"哪些词更值得先背"（词频排序）、"某词是否在大纲词汇范围内"（词形匹配，但要注意 2024 vs 2026 版本差异的不确定性，见第 8 节）。**不能**支撑"2026 年考试大纲结构/分值分布"这类结论（它没有这类信息）。

两者理论上是**互补**关系，是"日程表"与"教材列表"的关系，不是"同一份文件的两个副本"。这正是任务书标题所说"多源加权合并"的前提：两份来源分别提供正交的信息维度，未来做加权时不会因为"同源转载"而重复计权。

---

## 5. 落盘结构

### 5.1 新表（`data/english_vocabulary/eng1_vocabulary.sqlite`，未修改 `words`/`occurrences`/`stopwords`/`meta`/`delivery_log`/`v_top_words` 任何一行或任何一条 schema）

```sql
CREATE TABLE source_wordlists (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    sha256 TEXT NOT NULL,      -- 上游原始 netem_full_list.json 的 sha256（非本地 stripped 副本的）
    licence TEXT NOT NULL,
    retrieved_on TEXT NOT NULL
);

CREATE TABLE source_entries (
    entry_id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source_wordlists(source_id),
    rank INTEGER NOT NULL,
    word_form_original TEXT NOT NULL,   -- 保留原始大小写（比任务书示例多存的一列）
    word_form_norm TEXT NOT NULL,       -- 小写折叠键
    source_freq INTEGER NOT NULL,
    category TEXT,
    subcategory TEXT,
    other_spellings TEXT,
    UNIQUE(source_id, rank)
);
CREATE INDEX idx_source_entries_norm ON source_entries(source_id, word_form_norm);
```

只有 1 行 `source_wordlists`（`source_id='netem-5530-wordfreq'`）+ 5530 行 `source_entries`。**没有任何列存 `释义`。**

### 5.2 新增/修改的文件

| 文件 | 说明 |
|---|---|
| `tools/import_netem_source.py` | 读原始 JSON → 剥离释义 → 写 `netem_wordlist_stripped.json` → 建表并导入 |
| `tools/verify_netem_source.py` | 完整性校验 + 变异测试（`--mutation-test`） |
| `tools/netem_cross_validate.py` | 计算第 3 节的三个数字（+ lemma 校正的补充分析） |
| `tools/build_eng1_vocabulary.py` | **修了一处 scope 问题**，见第 6 节 |
| `data/english_vocabulary/netem_wordlist_stripped.json` | 已剥离释义的 NETEM 词表副本，是数据库构建的唯一可复现输入 |
| `data/english_vocabulary/eng1_vocabulary.sqlite` | 新增 `source_wordlists`/`source_entries` 两表 + 1 个索引 |
| `tests/test_netem_source.py` | 新增 5 条回归测试 |

### 5.3 给主控的登记建议（我不改 `data/materials.yaml`，仅在此提出建议值）

```yaml
- resource_id: eng1-netem-wordfreq-5530
  title: 考研英语（一）词频排序词表（NETEM，5530 条大纲词，基于约200套四六级/考研/专四专八真题词频排序）
  material_kind: vocabulary_wordlist   # ⚠️ 现有枚举里没有贴切的值（现有值：official_exam_notice/official_syllabus/
                                        #    outline_structure/past_exam_paper/reference_notes），建议新增此枚举值；
                                        #    若不想扩枚举，退而求其次可用 reference_notes。
  subjects: [eng1]
  acquisition: public_download
  rights:
    status: community_licensed          # ⚠️ 现有枚举里也没有完全贴切的值（见过 official_public/officially_published/
                                        #    scoring_rubric_restricted/unknown），这份数据许可证明确（CC BY-NC-SA 4.0
                                        #    + MIT），但发布方是个人维护的 GitHub 仓库、非官方机构，建议新增此值或由
                                        #    主控选一个最接近的既有值。
    licence: "数据 CC BY-NC-SA 4.0（署名-非商业性使用-相同方式共享）；代码 MIT。上游 README 自述释义部分
      经人工校对但可能引用第三方词典（如 little dict），本项目已剥离释义字段、不落盘释义文本。"
    licence_url: https://github.com/exam-data/NETEMVocabulary/blob/master/LICENSE
    may_store: true          # 仅限已剥离释义的词形/词频/分类等事实性字段
    may_display: true
    may_redistribute: false  # ShareAlike 条款要求以相同许可再分发；本项目是否需要对外重新分发未定，建议主控按项目
                              # 的实际分发范围决定，保守先设 false
    may_be_structured: true  # 已结构化（source_entries 表），因为是事实性词表数据，不是受版权正文
  source_tier: community_archive   # 与仓库里已有的 GitHub 社区仓库同类来源（如 cs408-index-2024-neville）保持一致口径
  storage:
    mode: local_file
    path: data/english_vocabulary/netem_wordlist_stripped.json   # 已剥离释义的版本，而非原始下载文件
    sha256: <见 tools/import_netem_source.py 运行输出 stripped_sha256，本报告未把它当"上游身份证"用，
             因为它是本项目自己生成的派生文件；上游身份证是下面这行的 sha256>
    upstream_sha256: 6d71a301321056291902bc4804e223c6926dca0d629a45076a6ca5adab185f62
    upstream_byte_size: 1106068
    url: https://github.com/exam-data/NETEMVocabulary/blob/master/netem_full_list.json
    retrieved_on: '2026-09-14'
  notes: "英语一第二份独立来源，词表级（现有 eng1-outline-toc-aus-zxhsd-2026 是目录级，两者覆盖层次不同、非同源）。
    与三年真题词库（eng1_vocabulary.sqlite/words 表）交叉验证：词形级重合率 23.50%（1299/5528），反向覆盖率
    59.10%（1877/3176，lemma 校正后 35.77%）。释义字段（第三方词典风险）已剥离，未落盘。"
```

（以上仅为建议值，字段名/枚举值是否需要在 `data/materials.yaml` 的 schema 里新增，由主控决定；我没有修改该文件。）

---

## 6. 一个意外发现：需要在 `tools/build_eng1_vocabulary.py` 里做的最小修复

添加 `source_wordlists`/`source_entries` 两张新表后，**触发了一个既有测试的回归**：
`tests/test_eng1_vocabulary.py::test_verifier_deterministic_check_and_mutations` 里
`python tools/build_eng1_vocabulary.py --check` 会失败（`CHECK FAIL expected_content_sha256≠actual_content_sha256`）。

**根因**：`build_eng1_vocabulary.py::static_content_hash()` 原实现是
```sql
SELECT type, name, COALESCE(sql,'') FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name
```
——它对"这个数据库里除 sqlite 内部对象外的**所有**对象"做哈希，而不是只对它自己管理的对象（`words/occurrences/stopwords/meta/delivery_log/v_top_words` 及 3 个命名索引）做哈希。任何人往同一个 `.sqlite` 文件里加新表/新索引（哪怕完全独立、完全不碰 `words` 等表的数据），都会让这个哈希改变，从而让这条历史测试变红——这是那条测试自身的 scope 设计问题，不是本轮改动的错误。

**修复**（`tools/build_eng1_vocabulary.py`，已提交本次改动，允许改 `tools/**`）：把 `static_content_hash()` 的 `sqlite_master` 查询从"排除 sqlite_ 前缀"改成"限定在一个显式白名单 `OWNED_SCHEMA_OBJECTS`"（即原本仅有的那些对象名）。这样：
- 对**没有**加过额外表的历史状态，哈希值与修复前完全一致（因为白名单里的对象集合，就是当年唯一存在的对象集合）——**不影响任何既有行为**。
- 对本轮加了 `source_wordlists`/`source_entries`/`idx_source_entries_norm` 之后的状态，`--check` 不再被这些无关表干扰。

我认为这是必要且最小的修复，而不是绕过检查——检查本身的意图（"验证 `words` 等表可从源 PDF 确定性重建"）完全没变，只是把"这个数据库文件里还有没有别的东西"这个不相关的问题排除掉。

---

## 7. 验证 + 变异测试

### 7.1 完整性校验（`tools/verify_netem_source.py`，我实测）
```
VERIFY PASS db_sha256=839d48be37d7716b1a12da04e3e2293868ee379b6e09a13dd198dae5498d0e2c
```
校验内容：两表存在、`source_wordlists` 关键字段非空、`source_entries` 恰好 5530 行、`rank` 是 1..5530 的无缺无重排列、`word_form_norm` 严格等于 `normalize(word_form_original)`、`source_freq` 非负、**schema 里没有释义类列名**、且**从已剥离释义的 `netem_wordlist_stripped.json` 重新计算一遍，逐 rank、逐字段与数据库内容完全一致**（可复现性检查）。

### 7.2 变异测试（我实测，3 种变异 + 复原哈希）
```
MUTATION PASS rank_value    verifier=RED detected=2 restore_sha256=839d48be37d7716b1a12da04e3e2293868ee379b6e09a13dd198dae5498d0e2c
MUTATION PASS deleted_entry verifier=RED detected=2 restore_sha256=839d48be37d7716b1a12da04e3e2293868ee379b6e09a13dd198dae5498d0e2c
MUTATION PASS casefold_key  verifier=RED detected=2 restore_sha256=839d48be37d7716b1a12da04e3e2293868ee379b6e09a13dd198dae5498d0e2c
MUTATION PASS baseline_unchanged restore_sha256=839d48be37d7716b1a12da04e3e2293868ee379b6e09a13dd198dae5498d0e2c
```
三种变异都在临时副本上进行（`tempfile.TemporaryDirectory`），原库全程未被写入；每次变异后校验器都变红（各检出 2 条错误：1 条是被改动字段本身的直接矛盾，1 条是与 `netem_wordlist_stripped.json` 重新对比出的整体不一致），且最后确认原库文件的 sha256（`839d48be...`）与变异测试开始前完全一致，证明变异只发生在副本上。

### 7.3 全量测试基线对比（我实测）

| | 开工前（round 21 开始时，我自己跑的第一次） | 结束时 |
|---|---|---|
| 测试数 | 193 | 198（+5，全部来自新增的 `tests/test_netem_source.py`） |
| 结果 | `OK`，exit 0 | `OK`，exit 0 |
| 失败数 | 0 | 0 |

**注意与任务书描述的出入**：任务书说"`tests/test_eng1_vocabulary.py` 此前有 2 条报错，是词汇库 v2 任务的中间状态"，但我在开工前第一次运行时，全部 193 条测试就已经是绿的（可能是主控在下发本任务前已经修复了那两条）。**我按自己实测到的"193 全绿"作为基线**，而不是凭空采信"2 条报错"的描述。

**过程中我确实引入过 1 次新失败**：加完 `source_wordlists`/`source_entries` 表后，`test_verifier_deterministic_check_and_mutations` 变红（见第 6 节根因分析），我随即在 `tools/build_eng1_vocabulary.py` 里做了最小 scope 修复，修复后重跑全量测试恢复到全绿。**最终交付状态相对于我自己的开工前基线，净增 5 条测试、0 条净回归**（中间那次失败已被修复并验证）。

---

## 8. 「我实测到了」vs「我推断」

**我实测到了**：
- SHA-256、字节数、条目数、字段名、去重后唯一数——全部亲自用 Python 重新计算过，与任务书给出的数值逐项核对一致。
- 交叉验证三个数字（重合率 23.50%、反向覆盖率 59.10%、分层重合率 60.00%/56.60%/45.70%）——直接跑 `tools/netem_cross_validate.py` 得到。
- lemma 校正后的反向覆盖率（35.77%）、撇号/连字符伪影抽样计数（83/97）——同样直接跑代码得到。
- 变异测试 3 项全部检测成功、原库 sha256 未变。
- 全量测试开工前 193 绿、中途 1 次回归、最终 198 绿。
- `words` 表所有 `word_form` 已经是小写（我查过，0 条例外），所以 NETEM 那边的大小写折叠是这次交叉比对里唯一需要处理大小写的一侧。

**我推断（未直接验证）**：
- "分层重合率随 rank 增大而下降"的原因（词频越低的词，真题里越可能以屈折形式出现）——这是基于观察到的数字趋势做的合理解释，没有逐词回归分析验证这个因果链。
- NETEM 语料库（约 200 套试卷）的具体时间跨度——我没有找到任何时间戳信息，"覆盖不到 ai-generated 这类新词"只是根据词表内容做的推测，不是仓库明确声明的事实。
- "其他拼写"字段里哪些是规范拼写变体、哪些是常见拼写错误——我只是凭直觉举了几个例子，没有逐条对照权威词典鉴别。

---

## 9. 没有把握的地方（至少 3 条）

1. **2024 vs 2026 考纲词表是否完全等同**：NETEM README 自述锚定"2024年"考研英语一考纲词汇表（5530 词），而我们项目里另一份来源是"2026 年"官方目录。考研英语一大纲词汇历年变动通常很小，但我没有找到任何文档证明 2024 版与 2026 版的 5530 词完全相同（也没有找到 2026 版官方词表可供逐词比对——这正是"目录级 vs 词表级""不能互相验证"的根源）。如果未来找到 2026 官方词表，这个"是否同一份词表"的假设需要重新核实。
2. **NETEM 词频语料库的时效性与构成**：README 只说"约 200 套四六级、考研英语、专四专八试卷"，没有给出具体年份范围、来源清单或抓取时间。词频排序（尤其是 `top500/1000/2000` 分层）在多大程度上反映"2026 年考试"的实际词频分布，是我无法验证的假设。
3. **"其他拼写"字段的数据质量**：154 条非空记录里混杂着规范的英美拼写变体（`centre/center`）和疑似拼写错误（`converzation/corse/rize`），我没有能力也没有在本轮任务范围内逐条鉴别，原样落盘，使用方需自行判断是否采信。
4. **1136 个"lemma 校正后仍不在 NETEM"的词，没有逐一分类**：只对含撇号（83个）和含连字符（97个）的子集做了抽样分类，剩下约 956 个（专有名词/超纲词/其他伪影的具体占比）只是目测举例，没有做穷举分类或人工逐词核实，因此"多少是超纲词 vs 多少是清洗残留"目前只有定性印象，没有精确切分的数字。
5. **`build_eng1_vocabulary.py::static_content_hash` 白名单是否完整**：我通过 `SELECT name FROM sqlite_master` 枚举了当前数据库里除 NETEM 新表外的全部对象（5 张表 + 1 个视图 + 3 个命名索引），并把它们写进 `OWNED_SCHEMA_OBJECTS` 白名单。如果未来 `build_eng1_vocabulary.py` 自身的 schema 演进（比如加新索引），需要记得同步更新这个白名单，否则可能出现"该脚本自己新增的对象反而被排除在校验之外"的静默漏检——这是我引入的一个新维护点，需要主控知悉。

---

## 10. 纪律遵守情况自查

- ✅ 只改了 `tools/**`（新增 3 个文件 + 修复 1 处 scope 问题）、`tests/**`（新增 1 个文件）、`data/english_vocabulary/**`（新增 stripped json + 新表）、`review/rounds/round-21-netem-import-claude.md`（本文件）。
- ✅ 未改 `data/materials.yaml`、`data/structured_materials/**`、`data/exam_questions/**`、`data/review_weights/**`。
- ✅ 未落盘 `释义` 文本（见第 2 节）。
- ✅ 未执行任何 `git` 命令。
- ✅ 全程用 `py -3.12`。
- ✅ 中文内容全部通过写 UTF-8 文件再用 Read 工具读取的方式核验，避免终端乱码误判（过程中确实遇到过一次终端吞字符导致 `print()` 输出乱码的情况，改用文件写入后恢复正常）。
- ✅ 未在项目仓库内留下过程中产生的临时探索性文件（已清理掉写在仓库根目录的 scratch 文件）。
