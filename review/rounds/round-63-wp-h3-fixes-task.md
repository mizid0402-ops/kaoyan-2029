# 任务书：WP-H3 决策者审查意见（续你上一轮的工作区改动）

决策者已审你第 61 轮的 diff，并在主工作区跑过全量：542 项，只有已知 2 项失败（决策者另修了
`tests/test_cli.py` 里裁剪注册表时漏掉的 `paper_shapes`，那一行不要动）。方向正确，下面几条要改。
遵守 `AGENTS.md`；只动下列文件，不改任何数据文件的数值。

## 必须改

1. **`tools/verify_408_index.py` 的 `_verify_paper_shape` 约 110 行**，违反 D7"一个函数一件事、约 60 行"。
   拆成有名字的辅助函数，例如：取卷面记录（出错返回问题列表）、逐题比对段（题型 / 答案字母 / 分值）、
   总分、独立重读答案。读取器表改为模块常量 `ANSWER_READERS = {"csgraduates_quiz_dom": extract_408_answers}`，并加一句注释说明"新来源格式 = 加一个读取器 + 在卷面登记里写名字"。
2. **`PaperRecord` 上的 `choice_count` / `choice_marks_each` / `essay_marks` 三个属性删掉**。
   它们把 cs408 的"`comprehensive_application` = 大题"假设带进了通用端口记录，只有 cs408 专用采集适配器
   `tools/build_408_index_v2.py` 在用。把需要的计算写成该工具里的本地辅助函数。
   改完按 `AGENTS.md` 12 条重新做一次 `924fb0e` 固定基线与新版在 2023–2026 的逐字节对照，写进报告。
3. **分值允许非整数正数**：英语一有 0.5 分题（索引里已有 `0.5`），卷面登记将来要能写。
   `marks_each` 与 `marks` 映射的值改为"有限正数（int 或 float，布尔除外）"；规格 `contracts/paper_shape.md` §3 同步。
   在 `tests/contract/test_paper_shape_port.py` 加一条 `marks_each: 0.5` 的正例、一条 `0`/负数/`.nan` 的负例。
4. **`tests/contract/test_exam_index_port.py` 的负例只断言 `assertTrue(verify(...))`**：任何一条无关问题都会让它通过，
   撤回对应检查也未必变红。改为断言问题列表里**含有针对该缺陷的那条信息**（子串即可），
   并把一个大测试拆成按场景命名的几个测试（D5 新年份、D6 出题单位、各负例），共用的临时工作区搭建放进辅助函数。
5. **`tools/verify_408_index.py` 模块 docstring** 被改掉了"其余字符串必须取自枚举集合"这层意思（`AGENTS.md` 13 条：删用户可见的约束说明要先报告）。
   恢复原句，只把"letters must be a single A-D"改成"answer letters are a single A-G letter, narrowed per section by the registered paper shape"。

## 建议改（顺手做）

6. `contracts/exam_index.md` 与 `contracts/paper_shape.md` 标题下加一行：所属模块（M5 / M5′，见 `docs/模块地图.md`）、实现文件、契约测试文件。

## 不做的

同第 61 轮任务书的"不做的"。不动 `tests/test_cli.py`、不动 `ky/storage/`、不动 `ky/__main__.py`。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_paper_shape_port tests.contract.test_exam_index_port tests.contract.test_workspace tests.test_exam_index tests.contract.test_check_questions_port
py -3.12 tools/verify_408_index.py
py -3.12 tools/mutation_test_408_index.py
py -3.12 tools/mutation_test_knowledge_weights.py
```

另：对第 4 条的每个负例，临时撤掉对应检查确认该测试变红，再还原（写进报告，还原后 `git diff` 只剩你的预期改动）。

## 报告

写到 `review/rounds/round-63-wp-h3-fixes-luna.md`，逐条说明落点与验收输出。全量：未跑。不提交。含中文的文件查 `???`。
