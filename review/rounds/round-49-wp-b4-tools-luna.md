# Round 49：WP-B′4 tools 去写死路径

## A. M5/M6 生效数据流水线

- `tools/verify_408_index.py`：增加 `--workspace`。默认目标来自注册表逐文件登记的
  `reference.exam_indexes`，不再 glob 索引目录；知识点成员校验调用登记的生效树，台账从
  `reference.ledger` 读取。台账内资料路径按 `Workspace.root` 解析。既有位置参数仍可显式指定
  要校验的索引文件。
- `tools/classify_questions.py`：增加 `--workspace`，知识树从
  `reference.knowledge_trees.cs408` 取得；显式 PDF、年份和输出参数仍然生效，非绝对输入/输出
  路径以 `Workspace.root` 解析。

## B. M21 408 讲解 PPT 生产线

- `tools/extract_cs408_bundle.py`：增加 `--workspace` 和可测试的 `build_bundle` 接口；树、附表、
  生效树、真题索引和输出目录均按注册表取值。导出 `tree_flat.csv` / JSON 时增加
  `is_effective` 与 `view_name`；manifest 同时记录补充视图名、kind、description 和实际登记路径。
- `tools/build_408_deck_scaffold.py`：增加 `--workspace` 和 `build_scaffold` 接口；输入、输出改用
  注册的产品目录。非生效节点标题及条目带可见的
  `【补充：非当年考纲，legacy_only_pending】` 标注，并展示补充视图名和 description。
- `tools/extract_408_questions_from_html.py`、`tools/extract_408_question_text.py`：增加
  `--workspace`；原始资料从 `materials.raw_root` 解析，索引清单使用登记文件，输出写到
  `products.cs408_lecture_workspace`。
- `tools/verify_408_question_extraction.py`：增加 `--workspace`；读取注册的产品目录和真题索引，
  并按规格从工作区根解析记录中的内嵌资料路径。
- `tests/test_cs408_lecture_pipeline.py`：在临时目录复制所需登记文件并改成另一组相对路径，运行
  bundle 与 scaffold；从实际树推导生效/补充 ID 集合，检查导出标志、视图元数据，以及每个非生效
  节点在对应讲解单元内有显式标注。测试不把当前 legacy 节点数量写成固定期望值。

## 验收摘要

- `py -3.12 tools/verify_408_index.py`：登记索引逐个为 `OK`，输出 `ALL INDEX FILES VERIFIED`，
  exit 0。
- `py -3.12 -m unittest tests.test_exam_index`：`Ran 9 tests`，`OK`。
- `py -3.12 -m unittest tests.test_cs408_lecture_pipeline`：`Ran 1 test`，`OK`。
- 五个 M21 脚本及分类器的 `--help` 均 exit 0，显示 `--workspace`。一次性抽取和验证工具未对
  原始资料或产品目录执行构建。
- 对 `tools/` 检查 `F:\workspace` 与 `F:/workspace`：无匹配。`git diff --check` 通过。
- 全量未跑，按仓库根 `AGENTS.md` 由决策者提交前统一运行。

## 规格歧义

未发现需要偏离 `contracts/workspace.md` 的地方。PPT bundle 是补充视图读模型，因此其中的附表属性
仍只随该视图导出；新增生效标志、视图名和 description 用于避免它被误读为纯生效树。

未运行会覆盖 `review/408知识点树与真题/` 的生产命令；本轮测试产物全部位于系统临时目录。
