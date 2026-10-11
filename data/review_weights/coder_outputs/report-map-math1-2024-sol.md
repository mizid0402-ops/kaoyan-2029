# 2024 年数学一知识树映射报告（sol）

## 结论

- 已独立完成 22/22 题编码，题号 1–22 无缺失、无重复。
- 置信度统计：high 18 题，medium 4 题，low 0 题。
- `null` 节点：0 题；未发现必须判为“疑似考纲外”的题目。
- 节点选择遵循任务书的 `chapter > section` 优先级，未使用结构性的“考试内容”或“考试要求”节点代替知识章节点。

## 输入与校验

- 题干来源：`math1_2024_ztbu.pdf` 与 `math1_2024_kmf.pdf`，两份来源均只读使用。
- 两份 PDF 的题号与主题交叉核对一致；另对原卷 5 页进行了渲染目视复核。
- 指定节点表共 66 个节点，所有输出 id 均可在该表中找到。
- 任务书声明节点表 SHA-256 为 `2c7d7dbbe194f5b1be701821a613b2dfb1cb4b7f265cd7de30d87ae02c942598`，当前指定 TSV 文件实算为 `8d9543368faf6fc8ebf45d8b548deffd59f15081253b94676788b95c0de56d82`。JSON 的 `node_table_sha256` 记录实算值；该差异不影响“仅从当前指定 TSV 取 id”的执行。

## 逐题映射

| 题号 | 主节点 | 辅助节点 | 置信度 | 判断依据 |
|---:|---|---|---|---|
| 1 | `math1.hs.ch03.chapter` | `math1.hs.ch01.chapter` | medium | 以变上限积分和换元判断函数奇偶性，跨积分学与函数性质。 |
| 2 | `math1.hs.ch06.chapter` | — | high | 第二类曲面积分的定向投影换算。 |
| 3 | `math1.hs.ch07.chapter` | — | high | 幂级数和函数求导后提取加权系数和。 |
| 4 | `math1.hs.ch02.chapter` | — | high | 一点处可导、导数极限与差商极限的关系。 |
| 5 | `math1.la.ch12.chapter` | `math1.la.ch10.chapter` | medium | 平面公共解对应方程组，借助系数矩阵和增广矩阵的秩判断。 |
| 6 | `math1.la.ch11.chapter` | — | high | 向量组线性相关性与秩。 |
| 7 | `math1.la.ch13.chapter` | — | high | 特征值、特征子空间及矩阵幂的迹。 |
| 8 | `math1.pr.ch17.chapter` | `math1.pr.ch16.chapter` | medium | 独立正态变量线性组合的分布。 |
| 9 | `math1.pr.ch18.chapter` | `math1.pr.ch17.chapter` | high | 条件分布构造联合分布后计算协方差。 |
| 10 | `math1.pr.ch17.chapter` | `math1.pr.ch16.chapter` | high | 独立连续随机变量函数的分布。 |
| 11 | `math1.hs.ch01.chapter` | — | high | 无穷小与幂指型极限。 |
| 12 | `math1.hs.ch05.chapter` | — | high | 多元复合函数链式法则与二阶导数。 |
| 13 | `math1.hs.ch07.chapter` | — | high | 傅里叶余弦级数系数及其渐近行为。 |
| 14 | `math1.hs.ch08.chapter` | — | high | 一阶微分方程的代换、分离变量与初值。 |
| 15 | `math1.la.ch14.chapter` | — | high | 对称矩阵对应二次型的半正定判定。 |
| 16 | `math1.pr.ch15.chapter` | `math1.pr.ch16.chapter` | medium | 独立重复试验的条件概率，二项分布为辅助表示。 |
| 17 | `math1.hs.ch06.chapter` | — | high | 平面区域上的二重积分及对称性。 |
| 18 | `math1.hs.ch05.chapter` | — | high | 曲面切平面与闭区域上的多元函数极值。 |
| 19 | `math1.hs.ch02.chapter` | `math1.hs.ch03.chapter` | high | 泰勒展开和二阶导数界为主，积分用于得到后续整体估计。 |
| 20 | `math1.hs.ch06.chapter` | — | high | 斯托克斯公式处理有向空间曲线积分。 |
| 21 | `math1.la.ch13.chapter` | `math1.la.ch10.chapter` | high | 矩阵递推、相似对角化与矩阵幂。 |
| 22 | `math1.pr.ch21.chapter` | `math1.pr.ch20.chapter` | high | 次序统计量估计、无偏性与均方误差准则。 |

## 不确定性说明

4 道 medium 题均不是题意不清，而是当前节点树只到章级，且题目本身跨章：第 1 题兼具函数性质与积分方法，第 5 题兼具矩阵秩与方程组几何，第 8 题兼具一维正态分布与多维变量函数，第 16 题兼具条件概率与二项分布。其 `primary_node` 按主要解题对象确定，辅助节点保留必要关联。
