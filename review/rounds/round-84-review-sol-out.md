# Round 84 Codex 复审：`a662c88`

基线：`git archive a662c88` 解到系统临时目录，复制了 Git 忽略的 `data/raw_materials/`。运行含 `git show 11cda18:...` 的契约测试时，设置 `GIT_DIR=F:/workspace/kaoyan-ai-system/.git`。只跑 `tests.contract.test_topic_weights_port`、聚合器 `--check` 和相关精确探针；未跑全量测试。P2 投影规则版本按本轮范围不评。

| 项 | 意见 | 证据与可复现输入 |
| --- | --- | --- |
| W2 硬链接原复现 | 不改 | `tools/aggregate_topic_weights.py:123-141,198-200` 先写目标同目录的 UUID 临时文件，再 `os.replace`。在临时工作区将登记的 `topic_weights.json` 以 `os.link` 链到工作区外 `outside.json`（内容 `outside sentinel`），运行 `--write --workspace <临时注册表>`：退出 0；外部文件仍为 `outside sentinel`，目标与外部文件不再是同一文件，`--check` 随后通过，也没有 `.<目标名>.*.tmp` 残留。第 83 轮原复现已关闭。 |
| 目录／只读／失败清理 | 不改 | 把已登记目标先建成目录：`--write` 退出 2，含 `expected a file`，目录保持、无临时文件。把目标建成文件后在 Windows 用 `os.chmod(target, stat.S_IREAD)` 设只读：`--write` 退出 2，旧内容仍为 `readonly sentinel`、无临时文件。再直接调用 `_replace_file`，将 `os.replace` 临时替成抛 `OSError("simulated replace failure")`：旧目标仍为 `existing sentinel`，同目录临时文件已清理。`finally` 的清理覆盖替换失败路径（`tools/aggregate_topic_weights.py:132-139`）。 |
| 跨卷与路径边界 | 不改 | 临时名由 `target.with_name(...)` 生成，源和目标父目录相同（`tools/aggregate_topic_weights.py:130-136`）；在模拟替换回调中实测 `source.parent == destination.parent` 且 `source.stat().st_dev == destination.parent.stat().st_dev`。因此正常文件系统下不会因跨卷而触发 `EXDEV`。`_write_target` 仍在创建临时文件前检查解析后的目标留在工作区内（`:109-120`）；本次未在另一个实际卷或映射盘符上运行，不扩大实测结论。 |
| W5 规格措辞 | 不改 | `contracts/topic_weights.md:73-79` 现明确“每个位置 JSON 类型相同；整数 `1` 与浮点 `1.0` 不同；同类型数值无容差比较，`0.0` 与 `-0.0` 相等”，与 `tools/aggregate_topic_weights.py:141-167` 先查 Python/JSON 类型再用 `!=` 的实现一致。原第 83 轮 `1`/`1.0` 反例已由规格明确为不同，未修改实际比较行为。 |
| W8 诱饵测试 | 不改 | `tests/contract/test_topic_weights_port.py:439-445` 在登记的学校卷旁放未登记、同身份的 `stray.json`，保存原字节并断言运行后不变。临时把 `_registered_indexes` 撤成目录扫描后，该测试失败，输出显示 `stray.json: write=1`；恢复登记路径后通过。诱饵确实能抓到第 83 轮指出的回退。 |
| P3 `depth` 说明 | 不改 | `contracts/projection.md:50,52` 两张知识点表都定义 `depth` 为“ID 点分段数 − 1”，明确不是沿 `parent_id` 到根的边数；与 `ky/projection/__init__.py` 现有 `len(parts) - 1` 一致。例如 `cs408.cn.chapter-01` 的父节点为 `NULL`、`depth=2`，现有列义不再需要读者猜测。 |
| 新测试撤修复 | 不改 | `py -3.12 -m unittest tests.contract.test_topic_weights_port`：14/14 通过；`py -3.12 tools/aggregate_topic_weights.py --check` 通过。仅在临时归档把 `main()` 的 `_replace_file(...)` 撤成旧 `output.write_text(...)`，新硬链接测试退出 1、断言失败；恢复源文件并核对其 Git blob 哈希与 `a662c88` 一致。W8 的目录扫描变异亦如上变红。文档措辞改动没有对应运行时代码回归测试，属适当范围。 |

**结论：PASS。** W2 已关闭；替换失败保留旧目标并清理临时文件。三条采纳的建议与实现一致，新增两条测试对对应回退均会变红。
