# 第 270 轮：M32 学完入队实现报告

## 改动

- 新增 `ky/review_intake/` 纯函数端口，按注册树语法确认可学点，生成 `ReviewItem`，并返回已在队列中的叶子及其 `review_id`。默认分钟数为 5。
- 新增 `ky learn` 子命令。它读取配置、注册表、所需知识树和当前队列后统一校验；成功时调用一次 `ReviewShardStore.write()`。`--dry-run` 不写队列。多科目显式参数按科目分组处理，最终合并为一次写入。
- 新增 `tests/contract/test_review_intake_port.py`，仅覆盖任务书列出的验收场景。
- `ky/__main__.py` 同时含 luna-a 对坏题停用的并行修改；本轮只新增独立的 `learn_main` / 参数解析器及命令注册，没有改动题库命令实现。

## 做法与分支选择

- 空队列通过 `read_state_sources().items` 读取；损坏 manifest、错误路径等仍由存储层报错，不会降级为空队列。
- 显式节点已处于 `queued` / `scheduled` 时违约退出 2；`--leaves-under` 遇到这两种状态时跳过并显示知识点 ID 与 `review_id`。无可加入叶子时显示跳过项并退出 2。
- 新 ID 检查整个已有队列（包括 `retired`）和本批已分配 ID；占用时从 `-2` 递增查找。
- 重复显式参数、参数解析错误和日期格式错误退出 3。知识树未登记、节点不在树中、跟踪节点、科目不在考及分钟数契约错误退出 2。
- 项目已有 `MAX_SINGLE_PASS_MINUTES` 上限为 30；`--minutes` 使用该上限及 ReviewItem 校验。

## 测试

按验收命令运行时，契约模块有一个测试夹具错误：辅助函数先创建了 `indexes/`，之后又用不带 `exist_ok` 的 `mkdir()`。未发现 `tests.test_cli` 的失败。修正夹具后按 `AGENTS.md` 只重跑受影响模块。

验收命令首次运行结果：

```text
Ran 68 tests in 93.833s
FAILED (errors=1)
FileNotFoundError: [Errno 2] No such file or directory: '<临时工作区>/indexes/eng1.json'
```

修正后受影响模块的原始输出：

```text
contract violation: math1.demo.chapter.item-a: knowledge point is already in the review queue as rv-current
contract violation: math1.demo.tracker: knowledge point is a tracker, not learnable
contract violation: reference.knowledge_trees.unknown: knowledge tree is not registered
contract violation: reference.knowledge_trees.eng1: knowledge tree is not registered
contract violation: math1: subject is not active in the exam
Ran 6 tests in 0.316s
OK
```

验收命令中的 `tests.test_cli` 已在首次组合运行中执行，未报告该模块失败；夹具修正后未重跑它。全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 歧义与选择

- 规格的分钟数未写上限；沿用 `ReviewItem` 的 `MAX_SINGLE_PASS_MINUTES`（30），非法值作为契约违约退出 2。
- 显式节点重复入队是违约；批量叶子中的既有活动项按规格要求跳过。批量结果全被跳过时，仍列出跳过项后以无可加入叶子退出 2。
- 并行编辑期间，luna-a 同时修改了 `ky/__main__.py` 的题库命令区域；本轮没有改动该区域。对 M32 新文件、测试文件及 `ky/__main__.py` 执行 `rg '\?\?\?'`，未发现连续问号标记。
