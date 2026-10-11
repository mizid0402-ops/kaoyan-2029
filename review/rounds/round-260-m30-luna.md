# 第 260 轮：M30 掌握度 + M17 能力画像页

## 改动

- 新增 `ky/mastery/` 纯函数端口：复习项档位、科目叶子掌握度 / 权重汇总、线性目标差距；不读取文件或 `last_self_rating`。
- M4 增加公开 `learnable_tree` / `LearnableTree`，集中提供有序可学树、叶子与跟踪节点；M17 进度映射与 M30 共用此结构。`parent_id`、`nearest_ancestor_with_scope` 与既有 `tree_parent` 保持不变。
- M17 增加 `ability_chart_data`、`render_ability` 与 `ky chart ability`，包含四档分布、目标差距、可折叠掌握树和薄弱点清单；复用既有主题与离线 HTML 写入方式。
- M0 注册 `weighted_mastery` feature，并仅在仓库 cs408 档案启用；加权科目要求登记有效的考频文件和该科映射，其他科目使用等权。
- 更新 M0/M17/M30 地图、README 快速查找与上手命令，并补充对应契约测试。

## 做法

M30 只接收已加载的 `KnowledgePoint`、`ReviewItem`、权重和日期，使用 M4 提供的共享树轮廓定位最近有效祖先；FSRS 项按稳定度分档，其他复习项按间隔分档。档位从不使用自评。权重按映射中最近祖先分摊给其可学叶子，再以 `Fraction` 汇总并按 ROUND_HALF_EVEN 展示。

能力页 CLI 一次读取复习队列、可用路线、知识树和（仅对启用加权的科目）考频映射。存在路线时起止日期都来自路线，否则都来自复盘设置。页面数据层只组装 M30 映射和有序目录树，渲染层负责四张卡片。

## 测试

执行命令：

```text
py -3.12 -m unittest tests.contract.test_mastery_port tests.contract.test_charts_port tests.contract.test_knowledge_tree_port tests.contract.test_workspace
```

测试输出原文：

```text
............................s........................
----------------------------------------------------------------------
Ran 53 tests in 2.798s

OK (skipped=1)
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）

## 歧义与选择

- M17 §4.5 已有可学树处理，而 M30 需要完全相同的叶子与跟踪节点边界。按任务书将该结构提升为 M4 的公开 `learnable_tree`，避免 M30 依赖 M17 私有代码或复制树算法；同时 M17 改为调用这个公共端口。
- 无知识树的科目在能力页显示无树、能力为空；存在知识树但缺少树语法则作为注册错误退出，不静默猜测语法。
- 报告仅记录合成测试与实现信息；未读取 `data/personal/`，未改动 `ky/schedule/`、`ky/models.py` 或 `ky/projection/`。未提交。
