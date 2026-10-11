# 任务：英语一词汇库 + **每日单词推荐器**（SQLite）

## 用户的实际需求（照这个来，不要加戏）

> 「我要的是如果每天背单词，按出现频率从高到低按顺序给我推荐 10-20 个单词。
> 至于从哪儿来、什么时候考、考过几次，**作为证据**。
> **不纳入每日学习的正文中。**」

所以有两层，**必须分开**：

| 层 | 内容 | 给谁看 |
|---|---|---|
| **每日产出** | **就是单词本身**，按频次降序，10–20 个 | **给用户看**——干净，不带出处、年份、次数 |
| **证据层** | 词从哪来、哪年考、考过几次、在哪一页 | **给系统用**——用户要看时才展开，**默认不出现在每日正文** |

**判断标准**：如果每日产出里出现了"2024 年阅读 Text 2 出现 3 次"这类字样，就是做错了。

## 数据来源（只读，不要修改）

- `%TEMP%\kaoyan-probe\claude2\dl\bv_e1_2024.pdf` / `bv_e1_2025.pdf` / `bv_e1_2026.pdf`（原卷排版，有文本层）
- `%TEMP%\kaoyan-probe\claude2\dl\lazy_e1_2024.pdf` / `lazy_e1_2025.pdf` / `lazy_e1_2026.pdf`（转排版，有文本层）

两份互为交叉验证。**只抽单词，绝不落盘句子、段落或文章原文。**

## 一、数据库

位置：`data/english_vocabulary/eng1_vocabulary.sqlite`（目录名你可调，须在项目内）

### 表 `words`（含证据，但它是证据层，不是每日正文）
| 列 | 说明 |
|---|---|
| `word_id` | 主键 |
| `word_form` | 小写归一后的词形 |
| `lemma` | 词元；无法可靠还原时等于 `word_form` |
| `pos` | 词性；判断不了留 null，**不要猜** |
| `total_count` | 总出现次数（**排序依据**） |
| `year_count` | 出现在几个不同年份 |
| `first_year` / `last_year` | 首末出现年份 |
| `is_stopword` | 0/1（the、of 等标 1） |

### 表 `occurrences`（证据层）
`word_id`、`exam_year`、`source_file`、`source_sha256`（现算）、`page`、`section`、`count_in_source`

### 表 `meta`
导出方法、脚本名与版本、生成时间、各来源 sha256、总词数、总词次，
以及**「只含词形与统计，不含原文」的声明**。

### 表 `delivery_log`（**这是"每天 10-20 个"能持续跑起来的前提**）
| 列 | 说明 |
|---|---|
| `delivered_on` | 日期（如 `2026-09-14`） |
| `word_id` | 外键 |
| `batch_index` | 该词在本批中的序号（1..N） |

没有这张表，"每天推荐下一批"就无从谈起——会反复推同一批词。

### 索引与视图
- `words.total_count DESC` 索引
- `words.year_count DESC` 索引
- 视图 `v_top_words`：按 `total_count DESC, year_count DESC, word_form ASC`
  （**排序必须稳定**，否则每次导出的顺序会变）

## 二、每日推荐器（用户真正要的东西）

新建 `tools/daily_words.py`：

```
py -3.12 tools/daily_words.py --count 15                  # 默认推荐 15 个（排除停止词）
py -3.12 tools/daily_words.py --count 15 --date 2026-09-14
py -3.12 tools/daily_words.py --count 15 --show-evidence   # 展开证据层
py -3.12 tools/daily_words.py --count 15 --include-stopwords  # 可选，默认关闭
py -3.12 tools/daily_words.py --reset                      # 清空 delivery_log
```

**行为**：
1. 从 `v_top_words` 里取**尚未投递过**的词，按频次降序取 `count` 个（默认 15，允许 10–20）
2. **默认输出只有单词**：一行一个，不带任何出处/年份/次数
3. 写入 `delivery_log`
4. 只有加 `--show-evidence` 时才输出 `word —— 出现在 2024/2025，共 N 次` 这类证据
5. 若剩余词不足 `count`，如实说明"已投递完，剩余 X 个"，不要重复投递
6. `--date` 用于补跑/回放；**同一天重复运行返回同一批词（幂等）**，不得生成新批次

**输出示例（严格照这个形态）**：
```
abandon
capacity
decline
...
（本批 15 个，累计已投递 15 / 共 3127）
```

**不要**在默认输出里加：词性、释义、例句、出处、年份、次数。
（释义以后可以单独做，**本轮不要求，也不许自己编**。）

## 三、抽取纪律

1. **分词规则**：英文用正则 `[A-Za-z][A-Za-z'-]*`，**在报告里写明规则**。
   不要用会吞掉连字符或所有格的方式而不说明。
2. **停止词**：库里**保留全部词**，用 `is_stopword` 标记，不做删除。
   **默认推荐策略已由用户定案：排除停止词**（`is_stopword=0` 才进每日推荐）。
   理由：用户要背的是实词，`the/of` 这类功能词会挤占每日 10–20 个名额。
   停止词仍完整入库、在证据层可审计。
   `--include-stopwords` 作为可选开关提供（默认关闭）。
3. **屈折还原要保守**：只做规则明确的（复数、-ed、-ing、比较级）。
   **拿不准就不要还原**，`lemma` 填原词形，并报告未还原比例。
   **绝不用"看起来像同一个词"去合并。**
4. **不得手工增删词条**：全部由脚本从来源产生，可复跑。
5. **两份来源差异**要报告：多少词只在 bv 出现、多少只在 lazy 出现。

## 四、交付物

1. `tools/build_eng1_vocabulary.py`——**确定性**（同输入两次运行内容一致；SQLite 若有时间戳
   导致字节不稳，请给出**内容哈希**的比较方法与证据）；支持 `--check`
2. 数据库文件（落盘项目内）
3. `tools/daily_words.py`（含 `--show-evidence` / `--date` / `--reset` / `--count`）
4. `tools/verify_eng1_vocabulary.py`——独立重算若干词频并与库对齐；
   校验 schema/索引/视图；**变异测试**（改一个词计数、删一条 occurrence、重复投递同一词）
   必须变红；给还原哈希
5. `tests/` 回归锁；`py -3.12 -m unittest discover -s tests -q` **必须全绿**
6. 报告 `review/rounds/round-16-eng1-vocab-codex.md`

## 五、报告必须包含

1. 抽取结果：总词数、总词次、去停止词后词数、跨年复现词数
2. **频次最高的 50 个词**（给含停止词与去停止词两个榜单）
3. 屈折还原：还原了多少、未还原比例、规则
4. 两份来源差异统计
5. **默认输出样例**（贴出 `--count 15` 的真实输出）**与** `--show-evidence` 的样例，
   证明每日正文里确实不含证据
6. 幂等性验证：同一天跑两次是否返回同一批词，证据是什么
7. 确定性验证的方法与结果
8. 变异测试结果 + 还原哈希
9. 「我实测到了」vs「我推断」
10. 没有把握的地方至少 3 条

## 六、纪律

- 可新建：`tools/build_eng1_vocabulary.py`、`tools/daily_words.py`、
  `tools/verify_eng1_vocabulary.py`、`data/english_vocabulary/**`、`tests/**` 新测试
- **禁止**修改：`data/structured_materials/**`、`data/review_weights/coder_outputs/**`、
  `data/materials.yaml`（如需登记来源在报告里提出）
- 不要执行 git
- 本机 `py` 启动器不回显输出，**必须用 `py -3.12`**（SQLite 用标准库 `sqlite3`）
- 终端吞中文，结果写 UTF-8 文件再读
- **绝不落盘真题原文**：库里只有词形与统计

最后用一句话回复：总词数/总词次 + 跨年复现词数 + `--count 15` 是否只输出单词 + 数据库路径 + unittest 结果 + 报告路径。
