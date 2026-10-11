# 阶段 2 交付报告（Luna 主实现者）

本轮只新建了 `ky/storage/**`、`ky/knowledge/**` 和新增测试文件；未修改
`ky/models.py`、`ky/schedule/*.py`、`tests/test_contracts.py`、`docs/**`、
`README.md`、`tools/**`，也未触碰 `F:\workspace\study`。

## 任务1

已实现确定性有界分片与清单索引，文件如下：

- `ky/storage/review_shards.py`
- `ky/storage/__init__.py`
- `ky/storage/__main__.py`
- `tests/test_storage.py`

实现要点：

- 默认按 `subject_id + SHA-256(review_id) 稳定桶 + 250 条上限` 分片；输入顺序、字典遍历顺序不影响结果。
- `manifest.yaml` 记录 schema/version、分片相对路径、分片 SHA-256、条目数、科目、桶号和 review_id 范围；清单哈希是原子提交点。
- 支持 `ReviewShardStore.load()`、`load_sharded_reviews()` 和 `load_review_queue()`；后者保留 `ky.models.load_review_items()` 的旧单文件兼容输入。
- 加载时逐片校验 YAML schema、分片哈希、条目字段、科目/桶/范围/数量，并做全局 `review_id` 去重；任一分片错误即整体失败，路径包含具体分片和条目字段。
- 写入采用版本化分片临时文件 → 完整校验 → 分片替换 → 清单临时文件校验 → 清单原子替换。清单替换失败时会清除本次未提交的新文件，旧清单仍指向旧分片。
- `WriteReport.affected_shard_hashes` 只报告受影响分片的旧/新哈希；删除分片的新哈希为 `None`。
- `py -3.12 -m ky.storage diagnose PATH` 是只读诊断命令，会枚举清单中的每个分片，不因第一处错误中断。

最终测试命令完整输出：

```text
PS F:\workspace\kaoyan-ai-system> py -3.12 -m unittest tests.test_storage
..
----------------------------------------------------------------------
Ran 6 tests in 36.765s

OK
exit code: 0
```

规模与写放大实测（CPython 3.12，Windows；在同一进程中完成初始生成后 GC，使用 `GetProcessMemoryInfo` 以 1 ms 间隔采样 Working Set；单文件/分片的 `peak delta` 是各自加载前基线到加载期间峰值的增量）：

| 条目数 | 单文件 YAML | 分片数 | 单文件加载耗时 | 分片加载耗时 | 单文件峰值增量 | 分片峰值增量 | 单文件更新需重写 | 分片更新实际写入 | 受影响分片 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 435,807 B | 32 | 1,055.2 ms | 1,117.6 ms | 23.05 MiB | 0.56 MiB | 435,807 B | 12,903 B | 1 |
| 5,000 | 2,187,807 B | 32 | 5,781.0 ms | 5,302.4 ms | 126.82 MiB | 0.80 MiB | 2,187,807 B | 49,698 B | 1 |

备注：本表中的分片加载只保留已解析的 `ReviewItem`，分片原始 YAML 在逐片返回后释放；同一进程的 Python 内存分配器会复用已提交页面，因此这里报告的是实测进程工作集峰值增量，不把它夸大为跨机器基准。分片格式的首写总字节数分别为 441,580 B 和 2,213,580 B，包含多份分片头和清单；收益发生在单条更新粒度。

## 任务2

已实现知识点结构化契约，文件如下：

- `ky/knowledge/knowledge_point.py`
- `ky/knowledge/__init__.py`
- `tests/test_knowledge_contract.py`

实现要点：

- 状态机固定为 `raw → extracted → reviewed → approved → superseded`；每条迁移要求合法发起者和必要的 source/evidence/replacement 前置条件，并保存连续的 `transition_history`。
- 知识点和证据均要求非空来源，来源必须包含 `path`、64 位 `sha256` 和定位信息；未知键拒绝并报告精确路径。
- `frequency.value` 只有 `writer="deterministic_script"` 且 `computed_by="deterministic_script"` 时可验证通过，并拒绝非有限数值；契约拒绝 AI 直接写频率。
- `source_kind: ai_generated` 不允许频率，证据只能是 `validation: guided`，不能进入频率/覆盖率/基线/预测/最终验收资格；提供 `eligible_for_frequency()` 和 `eligible_for_exam_metrics()`。
- 没有实现 AI 提取、频率统计、能力图谱或数据库写入。

新增契约测试完整输出：

```text
PS F:\workspace\kaoyan-ai-system> py -3.12 -m unittest tests.test_knowledge_contract
....
----------------------------------------------------------------------
Ran 4 tests in 0.001s

OK
exit code: 0
```

回归命令完整输出：

```text
PS F:\workspace\kaoyan-ai-system> py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler tests.test_cli
........................................................................................
----------------------------------------------------------------------
Ran 88 tests in 1.950s

OK
exit code: 0
```

## 未解决

1. **生产调度尚未接入清单路径。** 现有 `ky/models.py::load_review_items` 和 CLI 仍以旧单文件接口为主；本轮边界禁止修改既有实现，因此新增存储层由调用方显式使用 `load_review_queue()`。若要让正式 preflight 自动接受目录/manifest，**需要修改 `ky/models.py` 与 `ky/__main__.py`，最小 diff 是在输入路径为目录或 `manifest.yaml` 时转发到 `ky.storage.load_sharded_reviews()`，单文件继续走原函数；同时保留全量 fail-closed**。这不是本轮新增模块测试的失败，但属于正式生产路径集成项。
2. **跨文件事务的崩溃恢复仍是设计取舍。** 正常异常路径会清理未提交新分片；若进程恰好在分片替换完成、清单替换之前被强制终止，旧清单仍然有效，但可能留下未引用的版本化孤儿分片，需要后续 GC。没有引入目录级 generation/current 指针，以保持本轮最小实现。
3. **`writer` 是 Python 契约参数，不是外部身份认证。** 它能拒绝普通 AI 产物直接提交的 `writer="ai"`，但不提供进程级防伪；若未来把 AI 放进不可信服务边界，需要由编排器持有不可伪造的确定性脚本权限，而不是依赖字符串参数。
4. **规模测试只覆盖任务书要求的 1,000/5,000 条。** 没有把 20,000 条纳入最终测试命令，也没有声称分片格式在更大规模下已完成容量验收。

以上未解决项中，第 1 项是最需要审查者/编排器决定的接口集成项；本轮没有擅自修改受保护的既有文件。
