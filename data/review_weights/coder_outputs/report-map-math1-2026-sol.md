# 2026 年数学一试题知识树映射报告（sol）

## 结论

- 已完成 1—22 题全部编码，题号无缺失、无重复。
- 置信度统计：high 15 题，medium 7 题，low 0 题。
- `null` 统计：0 题；未发现必须判为“疑似考纲外”的题目。
- 所有节点均取自指定的 66 节点 TSV；按任务约定优先使用 `chapter` 节点，跨章题保留多个节点并指定一个主节点。

## 数据与核对方法

完整阅读了两份指定 PDF 的可提取文本层，并以两份解析互相校核题目所用方法。节点表磁盘文件采用 CRLF 换行；转换为 LF 后的 SHA-256 为任务书给出的 `2c7d7dbbe194f5b1be701821a613b2dfb1cb4b7f265cd7de30d87ae02c942598`。映射仅依据试题涉及的知识与求解方法，不依据其他 coder 的结果。

## 逐题映射

| 题号 | 主节点 | 其他节点 | 置信度 | 判断依据 |
|---:|---|---|---|---|
| 1 | `math1.hs.ch05.chapter` | — | high | 对隐式关系作偏微分并比较一阶偏导。 |
| 2 | `math1.hs.ch07.chapter` | — | high | 拆分幂级数并判断半径与端点敛散性。 |
| 3 | `math1.hs.ch02.chapter` | — | high | 辨析单调、极值及凹凸性的逻辑关系。 |
| 4 | `math1.hs.ch06.chapter` | — | high | 识别空间积分域并改写为球坐标三重积分。 |
| 5 | `math1.la.ch10.chapter` | — | high | 判断置换矩阵的逆和伴随矩阵性质。 |
| 6 | `math1.la.ch11.chapter` | `math1.la.ch12.chapter` | medium | 由列向量组线性表示关系推断方程组可解性。 |
| 7 | `math1.la.ch14.chapter` | `math1.la.ch13.chapter` | high | 用特征值确定二次型的秩、符号和标准形。 |
| 8 | `math1.pr.ch18.chapter` | — | high | 用均值、方差展开平方型期望并求最小值。 |
| 9 | `math1.pr.ch18.chapter` | `math1.pr.ch16.chapter` | medium | 结合线性分布变换以及均值、方差确定标准化参数。 |
| 10 | `math1.pr.ch15.chapter` | `math1.pr.ch16.chapter` | high | 从离散分布计算尾概率并比较条件概率。 |
| 11 | `math1.hs.ch05.chapter` | `math1.hs.ch04.chapter` | medium | 由叉乘构造向量场，再通过分量偏导计算散度。 |
| 12 | `math1.hs.ch01.chapter` | — | high | 用局部展开处理零比零型极限。 |
| 13 | `math1.hs.ch02.chapter` | — | high | 按参数方程求二阶导数。 |
| 14 | `math1.hs.ch03.chapter` | — | high | 计算无穷区间上的反常积分。 |
| 15 | `math1.la.ch13.chapter` | — | high | 求矩阵实特征值并比较其中最大者。 |
| 16 | `math1.pr.ch18.chapter` | `math1.pr.ch17.chapter` | medium | 用独立性建立协方差约束并求乘积期望。 |
| 17 | `math1.hs.ch05.chapter` | — | high | 求多元函数驻点并用二阶偏导判别极值。 |
| 18 | `math1.hs.ch08.chapter` | `math1.hs.ch05.chapter` | medium | 由全微分可积条件导出二阶关系，再结合初值解微分方程。 |
| 19 | `math1.hs.ch06.chapter` | — | high | 补线段后用格林公式计算第二类曲线积分。 |
| 20 | `math1.hs.ch02.chapter` | `math1.hs.ch03.chapter` | medium | 用单调性比较积分，并连续应用罗尔定理。 |
| 21 | `math1.la.ch11.chapter` | `math1.la.ch10.chapter` | medium | 先确定极大无关组，再借助低秩分解求矩阵幂。 |
| 22 | `math1.pr.ch21.chapter` | `math1.pr.ch16.chapter`、`math1.pr.ch18.chapter` | high | 构造无偏估计、计算方差并求最大似然估计。 |

## 低置信度与空节点说明

本次没有 low 或 `null` 项。第 6、9、11、16、18、20、21 题均跨越两个或以上章节，因此标为 medium；其节点本身均能在指定 TSV 中找到，不属于“疑似考纲外”。
