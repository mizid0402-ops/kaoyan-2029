# 第 263 轮：M30 掌握度与能力画像页实现初检 — PASS

范围：点名未提交改动，对照 mastery 规格、charts §8、260 任务书与交付报告；定点核对，不作全面审查。
决策者调整的页首/卡片说明不另复查；未联网、未读个人数据或仓库 outputs，未修改实现和测试。

## 既有审查项落实

- 259 M1：`cli._ability` 仅对档案含 weighted_mastery 的在考科目读取考频，其余传 weights=None。
  缺文件或缺科目映射走契约错误；workspace 接受新 feature，仓库仅给 cs408 启用。
- 259 M2：有路线取路线整对日期，无路线才读设置整对日期；mastery_gap 处理缺日期、exam<=start、时间 clamp 与单科 null 能力。
- 259 M3：叶子取最近有效复习项组，lapses=max(该组)，weak=lapses>=2；能力映射和薄弱表格直接携带这个数。
- FSRS 分档：item_level 用 stability；其他模式用 interval_days；不读取 last_self_rating，暂停/退役不参与档位。

## 其他规格落实

- M30 与 M17 共用公开 learnable_tree；按树语法确定层级、去除跟踪节点、保留树文件顺序。
- 叶子自挂多项取最低档；无自挂项时继承最近祖先；未学、零权重和无树情形有明确映射。
- 章权重按子树叶子均摊，用 Fraction 汇总、HALF_EVEN 输出四位；ability 取已巩固占比。
- 能力页四张卡片及折叠树、薄弱清单由 ability_chart_data/render_ability 装配；负差距显示“落后”。
- CLI 新增 ability；沿用离线 HTML 写入、固定日期文件名与显式打开行为；README、模块地图及公开端口登记已更新。

## 验证

- `PYTHONDONTWRITEBYTECODE=1`；只跑 `py -3.12 -m unittest tests.contract.test_mastery_port tests.contract.test_charts_port`。
- 原文：`Ran 11 tests in 0.702s`，`OK`；包含档位边界、目标差距、页面文字、重复生成/离线和权重错误路径。
- 一个综合合成探针，各核对项仅一次：小树中两项 FSRS 稳定度为 30/60、interval=1、lapses=2/5，
  另一项挂在祖先上；叶子权重 9/1。加权 ability=0.9000，等权=0.2500；FSRS 叶子为 consolidated，lapses=5。
- 同一探针：线性 expected=0.5000、该科 gap=+0.4000；另一科 ability/gap=null；数据层与 HTML 均正常，薄弱表格显示 5。
- 探针 HTML 写在系统临时目录，结束后清理；全量未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 必须改

无；本轮未发现日常路径算错或崩溃。

## 留给最终大检查

- `subject_mastery` 的 unknown_refs/tracker_refs 实际输出 knowledge_point_id，规格 §6 写 review_id；最终统一引用清单口径。
- 公共参数完整护栏、既有输出字节对照与页面视觉效果留给最终统一检查；本轮未作全面验证。

结论：PASS 仅代表本轮初检；不包含 FSRS 推进实现本身的验收，也不替代最终大检查。
