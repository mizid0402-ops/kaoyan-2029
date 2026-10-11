# Round 17：English-1 词频信号 v2

结论：方案 C 已完成。v2 数据库已重建，保留 v1 备份；词族只按规则置信度合并，排序使用 `family_total_count`，默认 daily 输出每个词族一行且不输出形态标签。

## 1. 改动范围与数据库结果

实际修改：

- `tools/build_eng1_vocabulary.py`：增加指导语行规则、`in_directions`、`is_direction_text`、`lemma_confidence`、`family_total_count`、落库 `stopwords` 表；构建版本为 `eng1-vocabulary-v2`。
- `tools/daily_words.py`：默认过滤停止词和指导语词；按整族频次排序；每族只输出一行，词形按自身频次降序；默认不输出出处、年份、次数或形态标签；增加 `--include-directions`。
- `tools/verify_eng1_vocabulary.py`：校验 schema、来源 hash、词次闭合、停止词一致性、指导语一致性、词族频次闭合，并提供临时库变异测试。
- `tests/test_eng1_vocabulary.py`：锁定 v2 schema、daily 过滤/幂等/词族排序、构建器 `--check`、verifier 和三类变异测试。

交付文件：

- 新库：`data/english_vocabulary/eng1_vocabulary.sqlite`
- v1 备份：`data/english_vocabulary/eng1_vocabulary.v1.sqlite.bak`
- 停止词源：`data/english_vocabulary/stopwords.txt`

v2 实测统计：3,409 个词形，25,073 个词次，2,919 个规则/不确定族键；v1 备份仍为 3,409 个词形、25,073 个词次，说明本轮没有新增原文或改变 token 抽取总量。

## 2. 去停止词、去指导语后的 TOP 25 对比

对比时，v1 也使用 v2 的 267 个停止词集合和 v2 实测的指导语词形集合过滤；v1 仍按单词形频次，v2 按词族合计频次。v2 一行中的多个词形属于同一规则词族。

|排名|v1 单词形|v2 词族行（family_total_count）|
|---:|---|---|
|1|ai 55|research  researchers（85）|
|2|science 55|texts（63）|
|3|research 48|work  works  working  workers  worked（63）|
|4|years 42|years  year（61）|
|5|artifacts 40|reading  readers  reads（55）|
|6|digital 37|ai（55）|
|7|researchers 37|science（55）|
|8|work 36|paragraph（51）|
|9|said 33|way  ways（50）|
|10|donkeys 33|ones（49）|
|11|make 32|parts（48）|
|12|nails 32|needed  needs（46）|
|13|information 31|shows  show  showed  showing（44）|
|14|history 30|point  pointing（44）|
|15|way 30|help  helped  helping  helps（42）|
|16|art 30|peoples（41）|
|17|children 30|artifacts（40）|
|18|according 29|make  makes（38）|
|19|change 29|technology  technologies（38）|
|20|paragraph 29|time  times（38）|
|21|public 28|direction（38）|
|22|technology 28|nails  nail（38）|
|23|time 28|digital（37）|
|24|two 28|fires  fire（36）|
|25|scientists 28|butterfly  butterflies（35）|

### 词族合计排序的两个直接证据

1. `point` 原形 4 次，`points` 38 次（另有 `pointing` 2 次）：v1 按 `point` 单形排名 962；v2 词族合计 44 次，排名 66。
2. `nail` 原形 6 次，`nails` 32 次：v1 按 `nail` 单形排名 733；v2 词族合计 38 次，排名 87。

这两例证明排序依据已从单一原形频次改为 `family_total_count`。headword 仍按族内词形自身频次选取，其他词形按自身频次降序跟随，不做词法形态标注。

## 3. 指导语判定规则与覆盖

判定是可复现的行级规则：先对每个 PDF 提取行，URL 区段替换为空格，再用下列不区分大小写的正则扫描完整行；命中某条规则的该行全部 token 标记为指导语 token。没有逐词人工标注，也没有写入原文。

```text
directions_label: \bdirections?\s*:
answer_sheet:     \banswer\s+sheet\b
read_following:   \bread\s+the\s+following\s+(?:text|passage)\b
choose_best:      \bchoose\s+the\s+best\s+(?:word|answer)\b
write_answer:     \bwrite\s+(?:your\s+)?answer\b
mark_answer:      \bmark\s+(?:your\s+)?answer\b
select_best:      \bselect\s+the\s+best\b
fill_blanks:      \bfill\s+in\s+the\s+blanks?\b
one_word:         \buse\s+one\s+word\b
```

覆盖结果：528 个指导语 token，占全部 25,073 个 token 的 0.021058509153（2.1058509153%）；涉及 59 个词形。数据库中 `words.in_directions` 等于该词形是否至少命中过一次，`occurrences.is_direction_text` 保存每个来源词次分组的行级结果。verifier 会重新读取六个 PDF、重算这些规则并逐来源逐词形比对。

## 4. 停止词落库与互校验

`stopwords.txt` 解析后的唯一词数为 267，位于要求的 150–300 区间；v1 的 `is_stopword=1` 为 125 个词形，本轮相对增加 142 个唯一停止词。v2 `stopwords(word_form)` 表与源文件集合完全相等，并且每个 `words.is_stopword` 都按该表重算。verifier 同时检查表集合、字段值和 `meta.stopword_count`，删除一条表记录但不改字段的变异会被标红。

## 5. 保守规则还原与词族合并

没有使用 nltk、WordNet、外部词典或网络词表。还原只使用代码中的有限规则：`use/used/uses/using` 的明确拼写规则、`-ies/-ers/-sses/-xes/-zes/-ches/-shes/-ses/-s/-ied/-ed/-ying/-ing/-iest/-est/-er` 这些确定或候选拼写规则，以及双辅音削减；没有硬编码不规则词元映射。候选不确定时保留 `lemma_confidence=uncertain`，其族键仍为自身词形；只有 `rule` 才以 `lemma` 作为族键。数据库中不保存形态类别，daily 输出也不带“复数/三单/过去式/现在分词”等标签。

实测：规则还原词形 1,080 个；不确定候选 129 个；合计记录还原候选 1,209 个，占 35.4649457319%；未还原比例 64.5350542681%。

以下 20 个是“已按规则归并、但仅靠规则仍可能错”的审计样本；它们是风险样本，不是外部词典确认。`family` 是归并后的全族频次。

|词形|规则 lemma|词形次数|family|
|---|---|---:|---:|
|following|follow|44|44|
|years|year|42|61|
|artifacts|artifact|40|40|
|points|point|38|44|
|researchers|research|37|85|
|directions|direction|36|38|
|donkeys|donkey|33|35|
|nails|nail|32|38|
|according|accord|29|29|
|scientists|scientist|28|32|
|countries|country|26|32|
|used|use|26|93|
|says|say|25|35|
|writing|writ|24|24|
|does|doe|22|22|
|elephants|elephant|22|26|
|paragraphs|paragraph|22|51|
|streaming|stream|22|31|
|pupils|pupil|21|21|
|words|word|21|26|

不确定候选确实未合并，例如 `answer -> answ`、`changed -> change`、`better -> bett`、`forest -> for`、`whether -> wheth`；这些只作为独立词形存在，不能影响其他词族的 `family_total_count`。

## 6. daily `--count 15` 实测输出

在清空该日期 delivery log 后运行 `py -3.12 tools/daily_words.py --count 15`，stdout 原样为：

```text
research  researchers
texts
work  works  working  workers  worked
years  year
reading  readers  reads
ai
science
paragraph
way  ways
ones
parts
needed  needs
shows  show  showed  showing
point  pointing
help  helped  helping  helps
```

检查结果：没有 `text`、`answer`、`sheet`、`following`、`directions`；15 行没有重复词根族；没有括号或任何形态标签；族频次从 85、63、63、61……单调不增。`--show-evidence` 仍可显式展开出处/年份/次数，默认输出不含这些字段。

## 7. 变异测试、确定性校验与回归

构建器只读检查：

```text
CHECK PASS content_sha256=52ed4710cd5c089ce3cb5ac5ce31bf95eeb77c8fe0a46ec1d3273e81d101544d
```

verifier：

```text
VERIFY PASS
```

三类变异都使 verifier 变红，并记录可还原的原库哈希；变异只发生在临时复制库，原库未被修改：

```text
MUTATION PASS in_directions verifier=RED detected=2 restore_sha256=abff85c7858af8f7616ccf707c38bcd8dea43305871564452d761eaa7ec8d87a
MUTATION PASS stopwords_row verifier=RED detected=3 restore_sha256=abff85c7858af8f7616ccf707c38bcd8dea43305871564452d761eaa7ec8d87a
MUTATION PASS lemma_family_count verifier=RED detected=2 restore_sha256=abff85c7858af8f7616ccf707c38bcd8dea43305871564452d761eaa7ec8d87a
MUTATION PASS baseline_unchanged restore_sha256=abff85c7858af8f7616ccf707c38bcd8dea43305871564452d761eaa7ec8d87a
```

其中三种变异分别是：把一个 `in_directions=1` 改为 0；删除一条 `stopwords` 表记录但不改 `is_stopword`；修改一个多成员规则族的 `lemma` 但不重算族频次。

完整回归：

```text
py -3.12 -m unittest discover -s tests -q
----------------------------------------------------------------------
Ran 193 tests in 70.305s

OK
```

## 8. 四条检验标准逐条结论

1. 通过：真实 `--count 15` 没有 `text/answer/sheet/following/directions`。
2. 通过：真实输出每行是一个规则族，`research/researchers`、`work/works/working/workers/worked` 等没有拆成多行。
3. 通过：真实默认输出只有词形，没有任何形态标签；专项测试拒绝括号形式。
4. 通过：排序 SQL 使用 `family_total_count DESC`，且 `point/points/pointing`、`nail/nails` 两个低原形高变体例子已给出旧排名与新排名。

## 9. 实测、推断与暂时无法验证

已实测：数据库行数/词次、指导语 token 数与比例、停止词表互校验、逐来源 occurrence 闭合、族频次闭合、daily 真实 stdout、三类变异红检、构建 deterministic check、193 个 unittest。

合理推断：去掉重复指导语和合并词族后，推荐目录更接近内容词的信号；“合理位置”依据是整族排序名次和合计次数，不等价于人工确认的考试重要性。

暂时无法验证：仅凭规则和 PDF 文本提取，不能证明每个词族在语义上一定同源；也没有人工逐行确认 PDF 提取出的所有指导语边界。为此不确定候选不参与合并，并保留 v1 备份供后续抽查。
