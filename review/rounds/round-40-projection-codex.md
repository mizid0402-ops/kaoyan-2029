# Round 40：本机只读 Web 投影复核与收尾

## 结论

Code review gate：**PASS**。A–E 已完成，8 条完成标准全部通过，没有未解决的 BLOCKER 或 MAJOR。

主控的大部分结果可以复现，但有两处不能照录：

1. `projection_meta` 实际为 **11** 行，不是交接文件所写的 10 行；其余四张表的 503、432、1059、79 均复现。
2. 连续构建的内容哈希确实相同，但本轮两次都是
   `ce487a4f1a047b2f3f0656548accf9377e9476cc00778ab82e7e152b9441ce7f`，不能复现交接中的
   `ef9e5a14…` 前缀。确定性结论成立，旧哈希值不能确认。

## 主控产出复核

先运行原有针对性测试：

```text
> py -3.12 -m unittest tests.test_projection -v
Ran 13 tests in 1.575s
OK
```

随后独立以只读 SQLite 连接查询，而不是引用交接中的数字：

```text
table_counts [('knowledge_points', 503), ('exam_questions', 432),
              ('question_knowledge_weights', 1059), ('topic_weights', 79),
              ('projection_meta', 11)]
kp_by_subject [('cs408', 410), ('eng1', 24), ('math1', 69)]
kp_by_scope [('chapter', 46), ('item', 261), ('section', 173), ('subject', 23)]
kp_by_tree_status [('extracted', 503)]
q_by_year [(2023, 69), (2024, 121), (2025, 121), (2026, 121)]
orphans [(0,)]
null_408_2026 [(7,)]
null_math1_2025 [(4,)]
views [('v_knowledge_points_by_subject',), ('v_question_coverage',)]
inputs 17
```

`cs408` 的 domain 独立列和修复后的 `v_question_coverage` 均由回归测试覆盖。没有发现为了通过测试而放宽验证的改动。

## A–E 实现

### A：一条命令启动显式不可变服务

新增 `ky/projection/serve.py`，确切命令是：

```powershell
py -3.12 -m ky.projection.serve
```

默认仅绑定 `127.0.0.1:8001`。入口固定生成：

```text
datasette serve --immutable <绝对数据库路径> --host 127.0.0.1 --port 8001
```

操作说明写入 `docs/projection.md`。服务入口未提供把正式投影切换为 mutable 的参数。

### B：HTTP 黑盒拒写

`tests/test_projection_service.py` 会构建临时投影，并给 Datasette 配置一条真实的 canned write query：

```sql
UPDATE projection_meta
SET value='MUTATED'
WHERE key='projection_schema_version'
```

测试通过 `py -3.12 -m ky.projection.serve` 启动服务并发出 HTTP `POST`。断言结果是 HTTP 403、响应包含
`Database is immutable`，随后以只读 SQLite 连接确认值仍为 `1`。

```text
> py -3.12 -m unittest tests.test_projection_service -v
test_authorized_canned_write_is_rejected_over_http ... ok
test_command_marks_database_immutable ... ok
Ran 2 tests in 2.043s
OK
```

这里使用的是能够在 mutable 模式成功写入的端点，因此 403 不是“端点不存在”、SQL 校验失败或缺少写权限造成的假阳性。

### C：依赖声明

`pyproject.toml` 新增 PEP 621 `[project]` 与实际外部 import 清点后的依赖：

```text
beautifulsoup4>=4.13,<5
datasette==0.65.4
pypdf>=6,<7
PyYAML>=6,<7
requests>=2.32,<3
sqlite-utils>=4.2,<5
```

本机解析 TOML 成功；实测版本为 Datasette 0.65.4、sqlite-utils 4.2.1、PyYAML 6.0.3、pypdf 6.14.2、
requests 2.32.3、beautifulsoup4 4.15.0。

### D：无投影时自动重建

删除正式派生文件后运行投影测试，`setUpModule()` 自动调用构建器；另有
`FreshEnvironmentRebuildTest.test_missing_projection_is_built_from_sources` 在全新临时目录中从不存在的路径开始构建。

```text
> Remove-Item data\projections\kaoyan_projection.sqlite
False  # Test-Path，确认已删除
> py -3.12 -m unittest tests.test_projection -q
Ran 15 tests in 4.363s
OK
```

### E：Windows 文件占用

构建器不再先删除旧投影，而是完成 `.building` 临时数据库后调用 `os.replace()`。替换遇到
`PermissionError` 时保留旧投影、删除临时文件并抛出 `ProjectionInUseError`，明确要求停止 Datasette。

本机实际启动服务并在服务存活时重建同一临时投影，结果是：

```text
rebuild_while_serving=FRIENDLY_REJECTION
error_type=ProjectionInUseError
message=Cannot replace projection ... Stop the Datasette projection service before rebuilding;
        Windows keeps the served SQLite file open.
```

另有回归测试验证错误信息、旧文件保留和 `.building` 清理。文档明确写明重建前先在服务终端按 `Ctrl+C`。

## 8 条完成标准的实际证据

### 1. 全量测试全绿

```text
> py -3.12 -m unittest discover -s tests -q
Ran 436 tests in 125.430s
OK
```

### 2. 可重建且连续两次内容哈希相同

两次分别执行：

```text
> py -3.12 -m ky.projection
projection rebuilt
  bytes                        368640
  knowledge_points             503
  exam_questions               432
  question_knowledge_weights   1059
  topic_weights                79
  inputs                       17
```

使用 `tests.test_projection._content_hash` 读取各表结构和有序行内容：

```text
build 1: ce487a4f1a047b2f3f0656548accf9377e9476cc00778ab82e7e152b9441ce7f
build 2: ce487a4f1a047b2f3f0656548accf9377e9476cc00778ab82e7e152b9441ce7f
```

### 3. 一条命令启动且 HTTP 写入被拒

命令为 `py -3.12 -m ky.projection.serve`；黑盒测试得到 403、`Database is immutable`，数据库值未变。

### 4. 树状态仍只有 extracted

```text
SELECT tree_status, COUNT(*) FROM knowledge_points GROUP BY 1;
=> [('extracted', 503)]
```

### 5. 未核实 marks 仍为 NULL

```text
2026 / cs408 / marks IS NULL => 7
2025 / math1 / marks IS NULL => 4
```

没有修改任何真题索引，也没有填入推测分值。

### 6. pyproject.toml 已声明依赖

TOML 解析和本机包版本清点均成功，声明见 C。

### 7. 只读变异测试变红并完整还原

只删除服务命令中的 `--immutable`，保持相同的 HTTP 测试：

```text
before_sha256=019e8b97cc040156d29c706cc37f7892a687b6852fe0252480d233a0ece12843
mutated_sha256=c3f115f67c2b14f6598ca0b8283304f82ed07afdb73ecc2d07ef2ade7e518b1c
mutation_test_exit=1
AssertionError: HTTPError not raised
Ran 1 test in 2.043s
FAILED (failures=1)
restored_sha256=019e8b97cc040156d29c706cc37f7892a687b6852fe0252480d233a0ece12843
restored_matches=True
```

变异后写请求返回成功，所以要求 403 的标准 3 确实变红；还原后同一模块 2/2 通过。

### 8. 现有 data 真相源未改

对 `data/structured_materials`、`data/exam_questions`、`data/review_weights`、
`data/english_vocabulary` 和 `data/materials.yaml` 共 94 个文件，以相对路径和原始字节计算聚合哈希：

```text
before: 9e2a41879b43c6f6623597604502219215a0a4708f18118bf114472b52b20892
after:  9e2a41879b43c6f6623597604502219215a0a4708f18118bf114472b52b20892
git diff --exit-code -- <上述路径> tools
=> forbidden_tracked_diff=NONE
```

`data/projections/kaoyan_projection.sqlite` 是本阶段允许新增的派生物。

## 我实测到了 / 我推断

### 我实测到了

- 436 个测试全绿，投影相关针对性测试 17 个全绿。
- loopback HTTP 服务返回 200；真实 HTTP 写请求在 immutable 服务上返回 403，数据库未变。
- 去掉 `--immutable` 后同一写请求不再抛出 HTTP 错误，测试变红；文件恢复哈希一致。
- Windows 服务运行时重建命中 `ProjectionInUseError`，停止服务后可以继续重建。
- 连续两次内容哈希相同；503/432/1059/79、所有分布、零孤儿、7+4 NULL 均由独立查询得到。

### 我推断

- `projection_meta` 的“10 行”与 `ef9e5a14…` 可能来自更早的中间实现或不同哈希算法；现有证据不足以确定原因。
- 固定 Datasette 0.65.4 可减少黑盒端点和错误语义漂移，但依赖解析器仍可能在未来选择兼容范围内的不同间接依赖。
- 同目录 `os.replace()` 在文件未占用时提供所需的替换语义；断电级持久性不在本轮验证范围内。

## 仍没有把握的地方

1. 本轮只在 Windows、Python 3.12 上实测；没有验证 Linux 或 macOS 的进程终止和文件替换细节。
2. “全新环境”实际验证的是投影文件和输出目录不存在时重建；没有新建隔离 venv 并从零下载所有依赖。
3. 确定性证据是表结构与有序行内容哈希，不承诺 SQLite 文件物理字节在不同 SQLite/Python 版本间一致。
4. 服务只验证了本机 loopback；未测试反向代理、局域网绑定或长期并发负载，这些也不属于阶段③的本机只读范围。
