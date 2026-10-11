# 2025 数学一真题节点映射报告（luna）

## 执行范围

已独立读取任务书、节点表，以及任务书列出的三份只读题源：

- `F:\workspace\kaoyan-ai-system\data\raw_materials\math1\exam_papers\math1_2025_ztbu.pdf`
- `F:\workspace\kaoyan-ai-system\data\raw_materials\math1\exam_papers\math1_2025_juying.pdf`
- `F:\workspace\kaoyan-ai-system\data\raw_materials\math1\exam_papers\math1_2025_kuaiyizhi.html`

PDF 文本层可以直接提取，未需要 `pypdfium2` 渲染兜底。映射仅使用 `math1_2025_nodes.tsv` 中存在的节点 ID；没有发现必须填 `null` 的题目，因此本次无“疑似考纲外”项。

## 节点表完整性

任务书声明的节点表 SHA-256 为 `2c7d7dbbe194f5b1be701821a613b2dfb1cb4b7f265cd7de30d87ae02c942598`，但本次实际读取的文件 SHA-256 为 `8d9543368faf6fc8ebf45d8b548deffd59f15081253b94676788b95c0de56d82`。实际文件包含表头加 66 个节点；JSON 的 `meta.node_table_sha256` 记录的是实际使用文件的哈希，而不是任务书中的声明值。

## 映射明细

| 题号 | primary_node | confidence | 依据摘要 |
|---:|---|---|---|
| 1 | `math1.hs.ch02.content` | high | 高阶导数判定极值、拐点，辅以变上限积分求导 |
| 2 | `math1.hs.ch07.content` | high | 无穷级数的绝对/条件收敛判别 |
| 3 | `math1.hs.ch01.content` | medium | 无穷远极限与导数、积分平均值之间的关系 |
| 4 | `math1.hs.ch06.content` | high | 二重积分区域分割和换序 |
| 5 | `math1.la.ch14.content` | high | 二次型正惯性指数 |
| 6 | `math1.la.ch11.content` | medium | 向量相关性、秩与平面交集几何 |
| 7 | `math1.la.ch10.content` | high | 矩阵乘积的秩性质 |
| 8 | `math1.pr.ch18.content` | high | 协方差、线性组合方差及约束优化 |
| 9 | `math1.pr.ch16.content` | high | 二项分布的泊松近似 |
| 10 | `math1.pr.ch22.content` | high | 已知方差均值的单侧假设检验 |
| 11 | `math1.hs.ch01.content` | high | 对数指数复合极限 |
| 12 | `math1.hs.ch07.content` | high | 傅里叶级数和函数 |
| 13 | `math1.hs.ch05.content` | high | 梯度与方向导数 |
| 14 | `math1.hs.ch06.content` | high | 格林公式与曲线积分 |
| 15 | `math1.la.ch09.content` | high | 奇异矩阵判定和行列式参数计算 |
| 16 | `math1.pr.ch15.content` | high | 独立事件的条件概率 |
| 17 | `math1.hs.ch03.content` | high | 有理函数部分分式积分 |
| 18 | `math1.hs.ch02.content` | high | 反函数二阶导数 |
| 19 | `math1.hs.ch02.content` | high | 中值定理与导函数严格单调性的等价性 |
| 20 | `math1.hs.ch06.content` | high | 高斯公式和曲面积分 |
| 21 | `math1.la.ch13.content` | high | 特征值重根与广义特征向量 |
| 22 | `math1.pr.ch16.content` | high | 条件二项分布与复合泊松分布 |

## 完整性统计

- entries：22 条。
- number：1–22，各出现一次，无缺号、无重复。
- confidence：high 20 条，medium 2 条，low 0 条。
- null：0 条。
- 所有 `primary_node` 和 `nodes` 均来自实际节点表。

## 输出文件

- JSON：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\mapping\map-math1-2025-luna.json`
- 报告：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\mapping\report-map-math1-2025-luna.md`
