# Round 50：WP-B′ 收尾

## 0. B′4 输出回归

恢复了 [build_408_deck_scaffold.py](../../tools/build_408_deck_scaffold.py) 中的生成注释、知识单元与所属章表格、来源支持度、子条目和真题命中行、带引用策略说明的真题定位表、无命中提示，以及考点提炼、原理与推导、易错点、真题印证占位和练习指向。保留了补充视图元数据与非生效节点标记。

恢复了 [extract_cs408_bundle.py](../../tools/extract_cs408_bundle.py) 覆盖报告的“命中次数最多的 40 个知识点”表、层级分布表和无命中说明；结构大纲的原有标题说明行也已恢复。`tree_flat.csv/json` 保留新增的 `is_effective` 与 `view_name` 列，清单保留补充视图名称及 description。

[test_cs408_lecture_pipeline.py](../../tests/test_cs408_lecture_pipeline.py) 从 `git show HEAD:<file>` 取旧版脚本，仅将旧版根目录重定向到临时目录，然后用同一批临时输入运行旧版与新版。测试比较树 CSV/JSON 的旧字段、真题索引、知识点映射、覆盖报告、清单旧字段及生效讲解单元；比较时只剥离本轮允许的补充元数据、非生效标记和索引年份说明。2 项测试通过。

索引年份说明的差异限于以下位置：

- 覆盖报告的“无命中不等于不考”行，从固定年份与套数改为由登记索引年份生成。
- 讲解单元无命中行的年份范围由生成的 `question_index.csv` 推导；原有“无命中不等于不考，只说明这四套里没出现”尾句保留。
- `tree_outline.md` 原有大纲来源说明未改。

检查了 B′4 其余迁移工具的可见输出代码。`extract_408_questions_from_html.py` 恢复了此前缩短的提取方法描述、综合题结构说明和完整 limitations 文案；校验器恢复了逐题选项、答案、样本文本、提取文本、报告汇总与讲解映射检查。校验器的样本从登记索引动态选取，当前样本数仍由年份集合推导。其余输出路径改为工作区相对路径是任务要求的路径变化。

## 1. P4 契约测试与数据清单

移除了 `tests/contract/` 中生效树、补充树、交集节点和索引文件数量的固定数据规模断言。快照与投影端口测试从登记树、补充视图和节点 ID 集合推导期望值；工作区测试从登记索引与 `data/exam_questions/*.json` 集合比对。通用 subject 测试改为从注册表取 subject，工作区结构测试用合成的 `alpha` / `beta` 标识。

新增 [test_data_manifest.py](../../tests/test_data_manifest.py)，集中记录当前版本的生效树、补充树、legacy 差集和索引数量，并包含任务要求的文件头注释。`tests/test_projection.py` 的真题行数期望也改为从登记索引的 entries 求和。

本节测试文件为 `tests/contract/test_projection_port.py`、`tests/contract/test_state_snapshot_port.py`、`tests/contract/test_workspace.py`、`tests/test_projection.py` 和新增的 `tests/test_data_manifest.py`。

## 2. V1 词汇关系形状

[vocab_channel.py](../../ky/schedule/vocab_channel.py) 的共享关系选择步骤返回关系名、列集合、过滤条件和参数；选中 `v_top_words` 或 `words` 后校验 `word_id` 与 `word_form`。SQLite 查询错误和缺列错误转为带关系名的 `VocabChannelError`。`import_delivery_baseline` 复用只读 `_connect`。

[test_vocabulary_port.py](../../tests/contract/test_vocabulary_port.py) 覆盖只有 `words(id INTEGER)` 的畸形库，以及两种关系名分别作为表和视图的情况。`contracts/vocabulary.md` 写明 `count == 0` 时在打开数据库前返回空批次。

遗留 `delivery_log` 排除桥接保持原状，供 WP-D 迁出状态后删除。

## 3. D7 可读性

- [projection/__init__.py](../../ky/projection/__init__.py) 新增 frozen `_ProjectionRows`，插入、写 meta/视图和写数据库步骤仅通过该对象传递解析行；仍先解析所有输入，再打开输出数据库。
- 词汇通道将关系与过滤选择集中到 `_select_relation`；预览查询和批次组装拆成具名步骤，`remaining_pool` 与 `preview_batch` 共用关系选择，`import_delivery_baseline` 共用连接函数。
- [knowledge_point.py](../../ky/knowledge/knowledge_point.py) 通过 `ContractError.message` 与 `.path` 构造 `KnowledgePointError`，避免路径在文案中重复；入口注释说明重复 YAML 键目前按文件级定位。

## 4. 模块地图

更新了 [模块地图.md](../../docs/模块地图.md) 的 M5/M6（B′4 注册路径与状态）、M7（保留 WP-D 遗留桥接说明）、M12 和 M15 行。未重写其他行。

## 5. 验收结果与说明

- `py -3.12 -m unittest tests.contract.test_projection_port tests.contract.test_state_snapshot_port tests.contract.test_workspace tests.contract.test_vocabulary_port tests.test_data_manifest tests.test_knowledge_contract tests.test_projection`：**61 项通过，1 项跳过**。跳过的是 Windows symlink 创建权限不足；junction 越界检查在 `test_5` 中运行并通过。
- `py -3.12 -m unittest tests.test_cs408_lecture_pipeline -v`：**2 项通过**，包含 HEAD 新旧输出对照。
- `py -3.12 tools/verify_408_index.py`：所有登记索引显示 `OK`，末尾为 `ALL INDEX FILES VERIFIED`。
- `py -3.12 -m py_compile ...`（改动 Python 文件）：通过。
- `git diff --check`：通过。改动文件未发现连续三个问号。`rg -n "\b(403|410|11|432)\b" tests/contract` 无匹配。
- 全量测试未运行，遵守根 `AGENTS.md` 的验证范围。

规格与任务书的张力在输出逐字节保留与 D5 去掉固定年份说明之间。处理方式是保留旧说明的语义与其余文字，只将年份范围替换为登记索引推导值；测试只对此年份说明做归一化，其余生效节点内容逐字节比较。提取报告中旧版固定 question ID 样本也改成索引驱动的代表样本，以避免把具体年份和题号继续写死。
