# WP-H4b 实现报告

## 改动文件

- `contracts/syllabus_migration.md`：定义 M25 纯函数端口、错误语义、CLI 与验收命令。
- `ky/review/syllabus_migration.py`：实现唯一版本链解析、队列迁移计划、去重和参照检查。
- `ky/__main__.py`：增加 `review-queue check` 与 `review-queue migrate`；读取映射时只使用
  `reference.syllabus_versions.<subject>.mappings`，apply 前校验目标版本树，写入通过
  `ReviewShardStore.write`。
- `tests/contract/test_syllabus_migration_port.py`：覆盖链解析、迁移结果、去重、悬空 ID、
  参照检查、CLI dry-run/apply/失败不写，以及登记两版大纲的集成演练。
- `docs/模块地图.md`：登记 M25，移除已实现的 H4b 缺口行。

## 设计落点

- 映射链解析会拒绝无路径、多路径、重复边和映射图中的环；相同起止版本返回空链。
- 队列迁移逐步应用每条映射；`targets()` 的来源成员校验用于发现悬空 ID，并在错误里合并
  列出所有悬空 `review_id`。拆分项按后续映射继续迁移。迁移保持其他科目和已退役项原样。
- 拆分复制原队列状态并重置 revision/defer_count；删除和拆分源项退役。每步按最早到期日、
  再按 `review_id` 去重，淘汰项递增 revision 并退役。
- `check` 读取各科生效树；`migrate --apply` 使用 `--to` 版本树检查完整迁移队列，通过后才
  调用原子写入。schema-1 已复习队列仍由存储层拒写保护。
- 集成演练先登记两个版本和映射，迁移队列，再切换 `knowledge_trees` 指针，验证 `check` 与
  `snapshot`。

## 验收

运行任务书指定命令：

```text
py -3.12 -m unittest tests.contract.test_syllabus_migration_port tests.contract.test_syllabus_mapping_port tests.test_cli tests.test_review_queue_advance
```

结果：`Ran 84 tests ... OK`。全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

已对本轮新增/修改的中文代码、规格、模块地图和契约测试执行连续问号占位符扫描，未发现匹配项。

## 建议

- 任务书第 3 节的集成示例在当前生效版本仍为 2026 时，应显式写成
  `migrate --subject S --from 2026 --to 2027 --apply`。因为既定默认值是 `effective_version(S)`，
  省略 `--to` 会解析为 2026→2026 空链。本轮集成测试已显式传入 `--to 2027`。
- 映射加载器现有来源成员判定足以支持本模块；本轮未改 `ky/knowledge/syllabus_mapping.py`。
