# 任务：修正英语一词汇库的频次信号（方案 C）

## 背景

`data/english_vocabulary/eng1_vocabulary.sqlite` 已建立（words 3409 / 总词次 25073 / 跨年复现 913）。
schema、每日输出形态（只出单词）、`delivery_log` 都已验证通过。

**但审计发现频次信号有两个缺陷，导致每日推荐质量差。**

## 缺陷一：频次最高的词是「试卷指导语」，不是「考试内容」

实测的实词榜首（去停止词后）：

```
text 57   ai 55   science 55   answer 54   new 52   use 51
research 48   part 46   one 45   following 44   may 42
world 42   years 42   people 40   artifacts 40
points 38   digital 37   researchers 37   directions 36
need 36   sheet 36   work 36   write 36   read 33   said 33
```

**`text` 排第一，是因为它出现在每道题的说明里**（"Read the following text"），不是因为它重要。
`sheet` 来自 ANSWER SHEET；`following`、`answer`、`directions` 同理。

**根因**：指导语在每套卷子里**逐字重复**，词次被系统性抬高。

## 缺陷二：屈折形式未还原，同一词根被算成多个词

`meta.unlemmatized_ratio = 1.0` —— **完全没做还原**。所以
`use / used / using / uses`、`year / years`、`research / researchers` 各自计数，
把一个词根的频次拆散了。

## 用户已定案：**两个都修（方案 C）**

---

## 你要做的

### 1. 区分「指导语词」与「正文词」

- 在 `words` 表加列 `in_directions`（0/1）
- 在 `occurrences` 表加列 `is_direction_text`（0/1），标明该次出现是否位于指导语中
- 判定方式**必须可复现**：用规则/词表，**不要手工逐个标词**
- 建议做法：把指导语特征串（如 "ANSWER SHEET"、"Directions:"、"Read the following text"、
  "Choose the best word"、"Write your answer"、"Mark your answer" 等）**按行定位**，
  落在这些行内的 token 标为指导语
- **把你实际用的规则完整写进报告**，并说明覆盖了多少 token

### 2. 扩充停止词表

- 当前只有 125 个，**明显过窄**：实测 `new / use / may / one / following / part / world / people`
  **全部未被标记**
- 扩到合理规模（考研英语常见停止词表，通常 150–300 个）
- **停止词表要落库**（新建表 `stopwords(word_form)`），不要只写死在代码里——
  将来网站要能查、能改
- `is_stopword` 与 `stopwords` 表**必须一致**（写完互相校验）

### 3. 屈折还原（保守，且必须标出哪些是猜的）

**用户对这一步有明确要求，照这个来：**

> 「诸如 study 的复数形式或者三单 studies，这些完全可以不考虑是什么形式，
> 因为最后给的结果都一样，所以只需要让 study 出现在背的名单中，
> 另外的 studies 可以写成 studies(复数、三单) 与 study 并列一行出现，
> 这样好处是不用统计 studies 这些另外形式的出现频率，有的话就在同一行加上就可以」

即：**词形变体不单独占推荐名额，而是与主形并列同一行。**
**但排序必须用词族合计频次**——否则原形低频、变体高频的词会排到很后面。
（用户自己补充指出了这个偏差：「某个词以变体高频出现但是不在频率清单排名靠前，这样是有失偏差的」）

具体：

- **主形（headword）**：词族里各形态中**出现次数最多**的那个形态，作为推荐行开头
- **变体**：同一词族的其他规则变体，跟在主形后面，**按各自词形频次降序排列**
- **`family_total_count`**：词族合计频次 = 各成员词形频次之和 → **这是排序依据**
- 推荐行**只出现一次**，输出形如：
  ```
  study  studies  studied
  ```
  **主形在前，变体随后。**

**不要标注形态。** 用户明确要求：

> 「只考虑变形高频，不需要考虑在什么情况下的变形，比如三单和复数，都是 studies，
> 但是我只需要看到 studies 的频率增高，然后在每天的学习目录里知道 study 是高频词，
> 变体有 studies 就基本 ok」

即：
- **不做三单/复数/过去式/现在分词的形态判定**——那种判定决定不了任何事，判错反而误导
- 变体只呈现**词形本身**，不带任何形态标签
- 这样也不需要任何词法分析，变体直接按**词形频次**排序即可

**其余纪律不变**：
- 只做规则明确的还原；新增 `lemma`（词族键）与 `lemma_confidence`（rule / uncertain）
- **只有 `rule` 的才合并进词族**；`uncertain` 的保留独立词条，并在报告里列出
- **绝不使用外部词典或凭记忆断定词元**——你没有词表来源，只能用规则
- 报告未还原比例，并**列出 20 个"归并了但可能错"的例子**供人工抽查

### 4. 重新生成数据库并保留旧版可比对

- 新版数据库用 `build_version = eng1-vocabulary-v2`
- **保留旧文件**（改名如 `eng1_vocabulary.v1.sqlite.bak`），便于对比改动前后
- `meta` 里要能看出：指导语 token 占比、停止词数、还原覆盖率

### 5. 每日推荐器的调整

`tools/daily_words.py` 默认策略（用户已定）：
- **排除停止词**（`is_stopword=0`）
- **排除指导语词**（`in_directions=0`）
- **按词族合计频次 `family_total_count` 降序排序**（不是按单个词形，也不是只按原形）
- **每行 = 一个词族**，形如：
  ```
  study  studies  studied
  ```
  主形在前，规则变体随后（**按词形频次降序，不标形态**）
- 新增 `--include-directions` 开关（默认关闭）
- `--show-evidence` 展开证据层（出处/年份/词族内各形态的次数）

**输出纪律不变：默认**只给词行，**不含**出处、年份、次数、形态标签。

**检验标准**：
1. 新版 `--count 15` 里**不应出现** `text / answer / sheet / following / directions` 这类指导语词
2. **不应出现两行同词根**（如一行 `use` 又一行 `using`）——它们必须在同一行
3. **不应出现任何形态标签**（如 `studies(复数、三单)`）——只给词形
4. 排序必须由 `family_total_count` 决定，并**给出两个例子证明**：
   某个"原形低频、变体高频"的词族，按旧口径会排很后，按新口径排到了合理位置

### 6. 验证与测试

- 更新 `tools/verify_eng1_vocabulary.py`：
  - `is_stopword` 与 `stopwords` 表一致性
  - `in_directions` 与 `occurrences.is_direction_text` 一致性
  - `lemma` 聚合后频次 = 其成员词形频次之和
- **变异测试**（必须变红并给还原哈希）：
  - 把某词的 `in_directions` 从 1 改 0
  - 从 `stopwords` 表删一个词但不改 `is_stopword`
  - 改一个 `lemma` 使聚合频次与成员和不符
- `tests/` 回归锁；`py -3.12 -m unittest discover -s tests -q` **必须全绿**

## 交付

1. 更新后的 `tools/build_eng1_vocabulary.py`（确定性、`--check`）
2. 新版数据库（v2）+ 旧版备份
3. 更新后的 `tools/daily_words.py`
4. 更新后的 `tools/verify_eng1_vocabulary.py`
5. 更新后的测试
6. 报告 `review/rounds/round-17-vocab-v2-codex.md`

## 报告必须包含

1. **改动前后的 TOP 25 对比表**（去停止词、去指导语之后）——直观看质量提升
2. 指导语判定规则全文 + 覆盖的 token 数与占比
3. 停止词表：新增了多少、总计多少
4. 屈折还原：还原覆盖比例、`rule` vs `uncertain` 条数、**20 个可能还原错的例子**
5. **新版 `--count 15` 的真实输出**（证明无指导语词、无同词根重复）
6. 变异测试结果 + 还原哈希
7. 确定性验证方法与结果
8. 「我实测到了」vs「我推断」
9. 没有把握的地方至少 3 条

## 纪律

- 可改：`tools/build_eng1_vocabulary.py`、`tools/daily_words.py`、
  `tools/verify_eng1_vocabulary.py`、`data/english_vocabulary/**`、`tests/**`
- **禁止**改：`data/structured_materials/**`、`data/review_weights/coder_outputs/**`、
  `data/materials.yaml`、`data/exam_questions/**`
- 不要执行 git
- 本机 **没有 `rg`**，用 Glob/Grep 工具或 `Get-ChildItem -Recurse`
- 必须用 `py -3.12`（标准库 `sqlite3`）
- 终端吞中文：结果写 UTF-8 文件再读
- **绝不落盘真题原文**：库里只有词形与统计

最后用一句话回复：新版总词数/总词次 + 去指导语后 TOP5 + `--count 15` 是否已无指导语词与同词根重复 + unittest 结果 + 报告路径。
