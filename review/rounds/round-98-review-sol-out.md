# Round 98 Codex 定向复审：`a84d9cf`

只看第 96 轮聚合工具换行阻断项及 I1、H1 两条建议。用 `git archive a84d9cf` 建系统临时副本，补入被忽略的原始资料及 `products` 空目录；测试只在归档内运行。未跑全量。

| 项目 | 意见 | 证据与可复现输入 |
|---|---|---|
| 聚合工具换行修复 | **不改** | `tools/aggregate_topic_weights.py:183-187` 对原来交给 `Path.write_text(..., encoding="utf-8")` 的同一段 JSON 文本，把其中 `\n` 换成 `os.linesep` 后交给 `replace_bytes`。在 Windows 的归档上运行 `py -3.12 tools/aggregate_topic_weights.py --write`，新产物为 **86,249 字节、2,972 个 CRLF**，SHA-256 `80378cb37ede30d181a8ae2b8db84afe17a8017d2354c66c7a80b86e36d978cd`，与第 96 轮对固定旧版 `8f31a05` 的实测三项完全相同。旧、新写法都对同一 JSON 文本做 UTF-8 编码，差异仅是文本流的换行转换。**非 Windows 未实机跑**：从代码推导，POSIX 的 `os.linesep` 为 `\n`，旧 `write_text` 对 `\n` 也不转换，故两版应逐字节一致；JSON 字符串中的换行被转义，`replace` 只作用于格式换行。 |
| 固定基线字节测试 | **不改** | `tests/contract/test_topic_weights_port.py:403-434` 固定 `git show 8f31a05:tools/aggregate_topic_weights.py`，断言旧源码包含 `def _replace_file(target: Path, text: str)`；两边从同一登记数据复制独立临时工作区，用相同当前公共依赖运行 `--write`，最后 `read_bytes()` 原样比较，不做行尾归一。归档中设置 `GIT_DIR=F:\workspace\kaoyan-ai-system\.git` 后单跑该测试通过 1/1；临时把新工具退回 `text.encode("utf-8")`，同一测试失败 1/1，差异显示旧版 CRLF / 新版 LF。归档没有 `.git`，设置 `GIT_DIR` 只是让固定提交可被读取，不影响两份写入输入。该测试对本次回退有实际鉴别力。 |
| I1：完整预检值断言 | **不改** | `tests/contract/test_planner_port.py:106-119` 现在同配置、同队列、同日期执行 `ky preflight --json`，删去其简版 `config` 后，对输入包整个 `review_clip` 做值相等断言；不是只检查 `subject_allocation` 键存在。归档中单跑该测试通过 1/1；临时把包的 `subject_allocation` 改为 `[]`，同一测试失败 1/1。 |
| H1：可信编排者的 `--plan` 路由 | **不改；保留已声明的限制** | `contracts/planner_port.md:7-15` 明写可信编排者不得把 AI 可写的 `staging/` 文件交给 `--plan`，并承认端口不检测。复用第 96 轮探针在本归档实测：staged `actor: human, input_hash: null` 仍被拒；但把一份裸日计划放在 `staging/day_plans/bare-plan.yaml`，调用 `day-plan submit --plan <该文件> --store <计划目录>` 仍返回 0，来源 `(1, human, null)` 且无输入包。这个调用违反了新写明的编排者规则；在决策者规定的“只有可信方能执行 apply”前提下，规则足以界定责任。`--plan` 允许无注册表的显式 `--store`，现在缺少可普遍识别 staging 的边界，延后到 E3b 定义 fail-closed 行为可以接受。若将来编排者实际能把 AI 路径路由到 `--plan`，须在集成验收中阻断，不能将当前文档视为代码防护。 |

**整体：PASS。** 第 96 轮的唯一阻断项已修复且有能在撤修复时变红的固定字节测试；I1 断言已补强。H1 保留的路由风险已明确写入信任边界，本轮按决策者的执行权限前提接受。
