# WP-H5：修复第 80 轮 B1 / B2 / B5 / B6 / B8

## 落点与证据

- **B1**：`--write` 只加载批次清单、编码者产出和生效树，不读旧 `topic_weights.json`；`--check` 才读取旧产物。`--write` 使用注册的 `reference.topic_weights`，文件缺失时可创建。`Workspace` 没有公开的缺失文件写入目标检查；工具的 `_write_target` 复用了其 `resolve` 后以 `relative_to(workspace.root)` 判越界的方式，并允许末端文件不存在。损坏 JSON、文件缺失两种临时工作区测试都完成 `--write` 后通过 `--check`。
- **B2**：规格和 `--check` 输出现说明采用无容差的数值相等；`0.0 == -0.0`。登记产物检查通过。
- **B5**：M6 拒绝非四位年份以及不匹配 `^[a-z][a-z0-9]*$` 的出题单位；`xidian` 正例通过。H3 校验工具有模块级 `YEAR` / `PAPER_SOURCE` 常量，但没有供 M6 依赖的共享端口；因此 M6 按规格保留一份校验定义，形成规则重复。分别暂时撤掉年份下界/上界检查与来源码正则后，对应负例均以 `ContractError not raised` 失败；恢复后测试通过。
- **B6**：写回器解析统考键与自命题键，并按 `(subject, year, paper_source, number)` 匹配；目标索引由工作区 `reference.exam_indexes` 登记项取得。临时工作区同时登记统考与自命题卷索引，只有自命题卷条目被写入。固定基线测试从 `git show 11cda18:tools/apply_knowledge_weights.py` 读取旧版，并断言其旧解析器标记；旧版与新版分别运行于同源、独立临时副本，所有登记索引写回后的字节映射相等。
- **B8**：规格明确 `nodes` 为空或为 null 时可省略 `confidence`；此类条目不投票。

## 验收

- `py -3.12 -m unittest tests.contract.test_topic_weights_port`：13 tests，`OK`。
- `py -3.12 tools/aggregate_topic_weights.py --check`：`topic_weights.json matches registered batches (numeric equality, no tolerance; 0.0 == -0.0)`。
- `py -3.12 tools/verify_408_index.py`：`ALL INDEX FILES VERIFIED`。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未提交。
