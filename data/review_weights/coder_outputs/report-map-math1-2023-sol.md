# 2023 年数学一知识树映射报告（sol）

## 结果概览

- 编码范围：第 1—22 题，共 22 题，无缺号、无重号。
- 置信度：high 20 题，medium 2 题，low 0 题。
- `null`：0 题；未发现必须判为“疑似考纲外”的题目。
- 节点选择：优先使用指定表中的 section 级 `*.content` 节点；跨章题保留多个相关节点，并以解题主线确定 `primary_node`。

## 输入核验异常

任务书标注节点表共有 66 个节点、SHA-256 为 `2c7d7dbbe194f5b1be701821a613b2dfb1cb4b7f265cd7de30d87ae02c942598`。对当前指定文件按原始字节核验后，表内实际有 66 个数据节点，但实际 SHA-256 为 `8d9543368faf6fc8ebf45d8b548deffd59f15081253b94676788b95c0de56d82`。JSON 的 `node_table_sha256` 记录实际值；节点表未被修改。

## 逐题映射

| 题号 | 主节点 | 其他节点 | 置信度 | 判断依据 |
|---:|---|---|---|---|
| 1 | `math1.hs.ch01.content` | — | high | 以无穷远极限确定斜渐近线的斜率和截距。 |
| 2 | `math1.hs.ch08.content` | — | high | 用特征根分析二阶常系数齐次方程解的有界性。 |
| 3 | `math1.hs.ch02.content` | — | high | 参数表示下分段求导并检查高阶可导性。 |
| 4 | `math1.hs.ch07.content` | — | high | 比较两个收敛级数的绝对收敛性质。 |
| 5 | `math1.la.ch10.content` | — | high | 分块矩阵初等变换与秩关系。 |
| 6 | `math1.la.ch13.content` | — | high | 用特征值及特征子空间判断对角化。 |
| 7 | `math1.la.ch11.content` | — | high | 求两个向量组张成空间的交集。 |
| 8 | `math1.pr.ch18.content` | `math1.pr.ch16.content` | medium | 期望是主考点，但计算依赖泊松分布；主次归属存在轻微交叉。 |
| 9 | `math1.pr.ch20.content` | — | high | 正态样本方差比的抽样分布。 |
| 10 | `math1.pr.ch21.content` | `math1.pr.ch16.content` | high | 构造尺度参数的无偏估计，并调用正态差分布。 |
| 11 | `math1.hs.ch01.content` | — | high | 通过局部最低阶项判断等价无穷小。 |
| 12 | `math1.hs.ch05.content` | — | high | 用偏导和梯度求曲面切平面。 |
| 13 | `math1.hs.ch07.content` | — | high | 计算傅里叶余弦系数及其级数。 |
| 14 | `math1.hs.ch03.content` | — | high | 定积分分割、平移换元与函数关系综合。 |
| 15 | `math1.la.ch11.content` | — | high | 由向量内积条件求线性组合系数。 |
| 16 | `math1.pr.ch17.content` | `math1.pr.ch16.content` | high | 独立随机变量联合事件概率与二项分布计算。 |
| 17 | `math1.hs.ch08.content` | `math1.hs.ch03.content`、`math1.hs.ch02.content` | medium | 建模主线是一阶微分方程，后半问还涉及积分上限函数和极值，主节点存在跨章取舍。 |
| 18 | `math1.hs.ch05.content` | — | high | 多元函数驻点与二阶极值判别。 |
| 19 | `math1.hs.ch06.content` | — | high | 高斯公式、三重积分与柱坐标计算。 |
| 20 | `math1.hs.ch02.content` | — | high | 二阶泰勒展开、中值性质和极值必要条件。 |
| 21 | `math1.la.ch14.content` | `math1.la.ch13.content` | high | 二次型合同化简及正交变换下的特征值判据。 |
| 22 | `math1.pr.ch17.content` | `math1.pr.ch18.content` | high | 二维分布、独立性、随机变量函数分布及协方差。 |

## 自检结论

所有 `nodes` 与 `primary_node` 均取自指定 TSV；22 条记录覆盖 1—22 且无重复。JSON 中没有 `null`，因此无需标注“疑似考纲外”。
