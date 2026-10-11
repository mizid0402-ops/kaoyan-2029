# Round 16：英语一词汇库与每日推荐器交付报告

## 结论

已按任务书建立 SQLite 词汇库、每日投递器、独立验证器和回归测试。每日正文与证据层分离：默认命令的 stdout 只有词形，一行一个；只有 `--show-evidence` 才展开来源证据。停止词没有删除，默认不投递；`--include-stopwords` 可显式加入。

## 1. 抽取结果

- 来源：`bv_e1_2024/2025/2026.pdf` 与 `lazy_e1_2024/2025/2026.pdf`，从指定 Temp 目录只读读取。
- 总词数（不同小写词形）：3409。
- 总词次：25073。
- 去停止词后可投递词数：3284；停止词词形数：125。
- 跨年复现词数（`year_count >= 2`）：913。
- 数据库只保存 `word_form`、统计字段、来源文件哈希及页/节定位字段；没有句子、段落或文章原文。

各文件抽取统计如下：

| 来源 | 年份 | 不同词形 | 词次 |
|---|---:|---:|---:|
| bv_e1_2024.pdf | 2024 | 1492 | 4278 |
| bv_e1_2025.pdf | 2025 | 1522 | 4206 |
| bv_e1_2026.pdf | 2026 | 1502 | 4152 |
| lazy_e1_2024.pdf | 2024 | 1511 | 4255 |
| lazy_e1_2025.pdf | 2025 | 1532 | 4076 |
| lazy_e1_2026.pdf | 2026 | 1523 | 4106 |

分词规则是任务书指定的 `[A-Za-z][A-Za-z'-]*`。在套用该正则前，仅从内存文本中移除 URL 非单词片段，避免页眉网址产生 `https`、`cn` 等伪词；所有单字母及停止词仍保留在库中并标记 `is_stopword=1`。数据库中的 `lemma` 保守等于原词形，`pos` 全部为 NULL：本轮没有未经词典验证的屈折合并，还原数 0，未还原比例 100%。

## 2. 频次最高 50 个词

格式为 `词形（总词次，出现年份数）`。第一榜保留停止词，第二榜按默认学习策略排除停止词。

### 含停止词

1. the（1454，3）  2. a（810，3）  3. to（719，3）  4. of（717，3）  5. and（576，3）
6. in（517，3）  7. c（275，3）  8. b（273，3）  9. that（267，3）  10. d（262，3）
11. is（240，3）  12. it（198，3）  13. as（181，3）  14. for（179，3）  15. on（169，3）
16. from（164，3）  17. are（158，3）  18. they（152，3）  19. their（141，3）  20. be（131，3）
21. s（128，3）  22. with（127，3）  23. have（123，3）  24. by（115，3）  25. can（105，3）
26. more（103，3）  27. but（99，3）  28. about（96，3）  29. an（92，3）  30. was（89，3）
31. at（83，3）  32. you（76，3）  33. what（71，3）  34. your（70，3）  35. we（68，3）
36. or（65，3）  37. i（64，3）  38. which（63，3）  39. this（59，3）  40. has（58，3）
41. not（58，3）  42. text（57，3）  43. been（56，3）  44. when（56，3）  45. these（55，3）
46. ai（55，2）  47. science（55，2）  48. answer（54，3）  49. new（52，3）  50. into（51，3）。

### 默认排除停止词

1. text（57，3）  2. ai（55，2）  3. science（55，2）  4. answer（54，3）  5. new（52，3）
6. use（51，3）  7. research（48，3）  8. part（46，3）  9. one（45，3）  10. following（44，3）
11. may（42，3）  12. world（42，3）  13. years（42，3）  14. people（40，3）  15. artifacts（40，2）
16. points（38，3）  17. digital（37，3）  18. researchers（37，3）  19. directions（36，3）  20. need（36，3）
21. sheet（36，3）  22. work（36，3）  23. write（36，3）  24. read（33，3）  25. said（33，3）
26. donkeys（33，1）  27. even（32，3）  28. make（32，3）  29. nails（32，1）  30. information（31，3）
31. also（30，3）  32. history（30，3）  33. way（30，3）  34. art（30，2）  35. children（30，2）
36. according（29，3）  37. change（29，3）  38. now（29，3）  39. paragraph（29，3）  40. public（28，3）
41. technology（28，3）  42. time（28，3）  43. two（28，3）  44. scientists（28，2）  45. around（26，3）
46. best（26，3）  47. good（26，3）  48. used（26，3）  49. countries（26，2）  50. different（25，3）。

这些词是“PDF 文本层中出现的词形”榜单，因此 `answer`、`following` 等试卷指令词也会进入统计；本轮没有擅自按语义删除它们。

## 3. 两份来源差异

按三年 bv 文件的词形并集与三年 lazy 文件的词形并集比较：bv 并集 3296 个、lazy 并集 3344 个；仅 bv 65 个，仅 lazy 113 个。按年份比较如下：

| 年份 | 仅 bv | 两者共有 | 仅 lazy |
|---:|---:|---:|---:|
| 2024 | 25 | 1467 | 44 |
| 2025 | 45 | 1477 | 55 |
| 2026 | 24 | 1478 | 45 |

差异可能来自两版排版、页眉/答案材料和文本层顺序，不把其中任一来源擅自当作绝对真值；两种来源的 `source_sha256` 都写入 `meta`，每条 `occurrences` 也保留对应来源哈希。

## 4. 每日推荐器真实输出

命令：`py -3.12 tools/daily_words.py --count 15 --date 2026-09-13`

真实 stdout：

```text
text
ai
science
answer
new
use
research
part
one
following
may
world
years
people
artifacts
```

以上 15 行没有年份、文件、页码、次数、词性、释义或例句；这就是默认每日正文。该批写入 `delivery_log`，默认过滤 `is_stopword=0`。

同一日期第二次运行的真实 stdout 逐字相同，仍为上述 15 行，没有新增投递记录。数据库约束为同日词批主键、同日序号唯一、以及 `word_id` 全局唯一，避免跨日期重复投递。

同日加 `--show-evidence` 的真实 stdout：

```text
text —— 2024/bv_e1_2024.pdf p.1 Section I x10; 2024/lazy_e1_2024.pdf p.3 Section II x9; 2025/bv_e1_2025.pdf p.1 Section I x10; 2025/lazy_e1_2025.pdf p.1 Section I x10; 2026/bv_e1_2026.pdf p.1 Section I x9; 2026/lazy_e1_2026.pdf p.1 Section I x9
ai —— 2024/bv_e1_2024.pdf p.7 Section IV x18; 2024/lazy_e1_2024.pdf p.7 Section IV x17; 2026/bv_e1_2026.pdf p.1 Section I x10; 2026/lazy_e1_2026.pdf p.1 Section I x10
science —— 2025/bv_e1_2025.pdf p.5 Section IV x12; 2025/lazy_e1_2025.pdf p.5 Section IV x11; 2026/bv_e1_2026.pdf p.3 Section II x16; 2026/lazy_e1_2026.pdf p.4 Section II x16
answer —— 2024/bv_e1_2024.pdf p.1 Section I x9; 2024/lazy_e1_2024.pdf p.1 Section I x10; 2025/bv_e1_2025.pdf p.1 Section I x9; 2025/lazy_e1_2025.pdf p.1 Section I x10; 2026/bv_e1_2026.pdf p.1 Section I x8; 2026/lazy_e1_2026.pdf p.1 Section I x8
new —— 2024/bv_e1_2024.pdf p.3 Section IV x10; 2024/lazy_e1_2024.pdf p.4 Section IV x10; 2025/bv_e1_2025.pdf p.4 Section IV x7; 2025/lazy_e1_2025.pdf p.5 Section IV x7; 2026/bv_e1_2026.pdf p.5 Section II x9; 2026/lazy_e1_2026.pdf p.5 Section II x9
use —— 2024/bv_e1_2024.pdf p.1 Section I x12; 2024/lazy_e1_2024.pdf p.1 Section I x12; 2025/bv_e1_2025.pdf p.1 Section I x9; 2025/lazy_e1_2025.pdf p.1 Section I x8; 2026/bv_e1_2026.pdf p.1 Section I x5; 2026/lazy_e1_2026.pdf p.1 Section I x5
research —— 2024/bv_e1_2024.pdf p.3 Section IV x2; 2024/lazy_e1_2024.pdf p.4 Section IV x2; 2025/bv_e1_2025.pdf p.3 Section IV x12; 2025/lazy_e1_2025.pdf p.4 Section IV x12; 2026/bv_e1_2026.pdf p.3 Section II x10; 2026/lazy_e1_2026.pdf p.4 Section II x10
part —— 2024/bv_e1_2024.pdf p.2 Section II x8; 2024/lazy_e1_2024.pdf p.3 Section II x8; 2025/bv_e1_2025.pdf p.2 Section II x9; 2025/lazy_e1_2025.pdf p.3 Section II x9; 2026/bv_e1_2026.pdf p.2 Section II x6; 2026/lazy_e1_2026.pdf p.3 Section II x6
one —— 2024/bv_e1_2024.pdf p.1 Section I x12; 2024/lazy_e1_2024.pdf p.1 Section I x13; 2025/bv_e1_2025.pdf p.5 Section IV x7; 2025/lazy_e1_2025.pdf p.5 Section IV x7; 2026/bv_e1_2026.pdf p.1 Section I x3; 2026/lazy_e1_2026.pdf p.1 Section I x3
following —— 2024/bv_e1_2024.pdf p.1 Section I x8; 2024/lazy_e1_2024.pdf p.1 Section I x8; 2025/bv_e1_2025.pdf p.1 Section I x10; 2025/lazy_e1_2025.pdf p.1 Section I x8; 2026/bv_e1_2026.pdf p.1 Section I x5; 2026/lazy_e1_2026.pdf p.1 Section I x5
may —— 2024/bv_e1_2024.pdf p.5 Section IV x6; 2024/lazy_e1_2024.pdf p.5 Section IV x6; 2025/bv_e1_2025.pdf p.4 Section IV x11; 2025/lazy_e1_2025.pdf p.5 Section IV x11; 2026/bv_e1_2026.pdf p.3 Section II x4; 2026/lazy_e1_2026.pdf p.4 Section II x4
world —— 2024/bv_e1_2024.pdf p.1 Section I x5; 2024/lazy_e1_2024.pdf p.1 Section I x4; 2025/bv_e1_2025.pdf p.5 Section IV x11; 2025/lazy_e1_2025.pdf p.5 Section IV x7; 2026/bv_e1_2026.pdf p.1 Section I x8; 2026/lazy_e1_2026.pdf p.1 Section I x7
years —— 2024/bv_e1_2024.pdf p.1 Section I x5; 2024/lazy_e1_2024.pdf p.1 Section I x5; 2025/bv_e1_2025.pdf p.1 Section I x5; 2025/lazy_e1_2025.pdf p.1 Section I x5; 2026/bv_e1_2026.pdf p.3 Section II x11; 2026/lazy_e1_2026.pdf p.4 Section II x11
people —— 2024/bv_e1_2024.pdf p.1 Section I x11; 2024/lazy_e1_2024.pdf p.1 Section I x8; 2025/bv_e1_2025.pdf p.5 Section IV x4; 2025/lazy_e1_2025.pdf p.6 Section IV x4; 2026/bv_e1_2026.pdf p.6 Section II x7; 2026/lazy_e1_2026.pdf p.6 Section II x6
artifacts —— 2024/bv_e1_2024.pdf p.11 Section IV x14; 2024/lazy_e1_2024.pdf p.9 Section IV x13; 2025/bv_e1_2025.pdf p.9 Section IV x7; 2025/lazy_e1_2025.pdf p.8 Section IV x6
```

这组对比直接证明证据默认不出现在每日正文，而是由开关显式展开。`--reset` 会清空 `delivery_log`；剩余不足 `--count` 时，已投递词不重复，剩余数量从 stderr 如实提示。

## 5. 确定性、独立校验与变异测试

- 初次构建数据库文件哈希：`24c69b604fb0e0a36af7693ec6a743fdde1c57b312783fe812b5d37c127f55d3`。
- `py -3.12 tools/build_eng1_vocabulary.py --check`：PASS。构建拥有的静态内容哈希：`549affde7267d2fb70bf03fdb37a759c4bd30e86bb3a27c652ec4676838e3e30`。
- 投递后文件哈希变为 `33263016c29788f5befa9f393068eadca69443ea5b49570436f24d5d83ed7f05`，这是正常的 `delivery_log` 运行时变化；静态内容哈希仍通过。
- `py -3.12 tools/verify_eng1_vocabulary.py`：`VERIFY PASS words=3409 tokens=25073 cross_year=913`，并还原确认数据库哈希为 `33263016c29788f5befa9f393068eadca69443ea5b49570436f24d5d83ed7f05`。
- 独立验证器重新读取六个 PDF、独立重算 token 计数，检查 schema、索引、视图、来源哈希、外键、词形字段和稳定排序。
- 变异测试三项均被检测：改一个 `total_count`、删一条 `occurrences`、重复投递同一 `word_id`；原数据库在测试后哈希未变化。

## 6. 回归测试

新增 `tests/test_eng1_vocabulary.py`，锁定 schema/排序、默认排除停止词、默认正文不含证据、`--show-evidence` 展开证据、同日幂等、静态构建检查、独立验证器和变异测试。

最小范围：`py -3.12 -m unittest tests.test_eng1_vocabulary -q` → 3 tests，OK。

## 7. 实测与推断边界

### 我实测到了

- 六个来源文件存在且有文本层；数据库统计、来源 sha256、真实 CLI 输出、同日重复输出、静态构建检查和独立验证结果均已实际运行。
- 默认 `--count 15` 的 stdout 是 15 个词形行，未出现年份、出处、次数或证据分隔符。
- `--show-evidence` 同一批才出现年份、文件、页码和次数；默认停止词过滤与 delivery_log 写入实际通过测试。

### 我推断或暂时无法完全验证

1. bv 与 lazy 的差异只能说明两个文本层/排版来源的差异，不能单凭本库断言哪一版更接近官方印刷原卷。
2. 本轮不做词元还原和词性猜测，因此 `research`/`researchers` 等屈折或派生形仍是独立词形；这是保守策略，不是语言学词元真值。
3. `occurrences.page` 是该词在该来源中的首次页，`count_in_source` 是该来源全文总次数；它不是每一次出现的逐位置坐标。
4. 停止词集合是为默认学习投递定义的工程集合，不等同于某一本官方英语教学词表；停止词仍完整入库并可用 `--include-stopwords` 投递。
5. `generated_at` 使用确定性的任务执行日期标记，以保持构建内容可复现；它不是精确到秒的墙钟审计时间。

## 8. 交付路径

- 数据库：`data/english_vocabulary/eng1_vocabulary.sqlite`
- 构建器：`tools/build_eng1_vocabulary.py`
- 每日推荐器：`tools/daily_words.py`
- 独立验证器：`tools/verify_eng1_vocabulary.py`
- 回归测试：`tests/test_eng1_vocabulary.py`
