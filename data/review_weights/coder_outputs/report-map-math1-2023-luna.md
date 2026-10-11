# Math I 2023 节点映射报告（luna）

## 范围与来源

- 题目来源：`F:\workspace\kaoyan-ai-system\data\raw_materials\math1\exam_papers\math1_2023_qihang.pdf`
- 合法节点表：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\mapping\tasks\math1_2023_nodes.tsv`
- 当前节点表 SHA-256：`8d9543368faf6fc8ebf45d8b548deffd59f15081253b94676788b95c0de56d82`
- 任务书声明的节点表 SHA-256：`2c7d7dbbe194f5b1be701821a613b2dfb1cb4b7f265cd7de30d87ae02c942598`
- 说明：当前文件按字节计算的哈希与任务书声明值不一致；本映射未修改节点表，并以当前文件中实际存在的 66 个 node_id 做合法性校验。
- 未读取或引用其他 coder 的产出。

## 结果

| 题号 | nodes | primary_node | confidence | 判断依据 |
|---:|---|---|---|---|
| 1 | `math1.hs.ch01.content` | `math1.hs.ch01.content` | high | 斜渐近线的斜率和截距由无穷远处的函数极限确定，核心是函数极限与渐近性质。 |
| 2 | `math1.hs.ch08.content` | `math1.hs.ch08.content` | high | 通过二阶常系数线性微分方程的特征根讨论全轴有界解，属于常微分方程通解与性质。 |
| 3 | `math1.hs.ch02.content` | `math1.hs.ch02.content` | medium | 参数方程确定的函数需要比较一阶、二阶导数在连接点的存在性和连续性，归入一元函数微分学。 |
| 4 | `math1.hs.ch07.content` | `math1.hs.ch07.content` | high | 利用两个收敛级数的差以及绝对收敛的定义判断等价关系，核心是无穷级数的收敛性。 |
| 5 | `math1.la.ch10.content` | `math1.la.ch10.content` | high | 对分块矩阵实施初等变换并比较秩，所考概念是矩阵的秩及其运算性质。 |
| 6 | `math1.la.ch13.content` | `math1.la.ch13.content` | high | 通过特征值重数与线性无关特征向量个数判断能否相似对角化，属于特征值与特征向量。 |
| 7 | `math1.la.ch11.content` | `math1.la.ch11.content` | high | 将同一向量分别置于两组向量的线性表示中并比较系数，核心是向量的线性表示与线性关系。 |
| 8 | `math1.pr.ch16.content` | `math1.pr.ch16.content` | high | 对泊松型离散随机变量按取值分解绝对偏差的数学期望，属于一维随机变量及其分布。 |
| 9 | `math1.pr.ch20.content` | `math1.pr.ch20.content` | high | 由正态总体样本方差的卡方分布构造方差比的 F 分布，属于数理统计基本概念与抽样分布。 |
| 10 | `math1.pr.ch21.content` | `math1.pr.ch21.content` | high | 先求样本差的绝对值期望，再选常数使估计量无偏，直接考查参数的无偏估计。 |
| 11 | `math1.hs.ch01.content` | `math1.hs.ch01.content` | high | 比较两个函数在零点附近的最低阶展开系数来确定等价无穷小，属于极限与无穷小。 |
| 12 | `math1.hs.ch05.content` | `math1.hs.ch05.content` | high | 用曲面在指定点的两个偏导数写切平面，核心是多元函数的偏导与全微分几何应用。 |
| 13 | `math1.hs.ch07.content` | `math1.hs.ch07.content` | high | 利用周期函数的余弦级数系数公式并求系数平方和，属于傅里叶级数及其收敛相关内容。 |
| 14 | `math1.hs.ch03.content` | `math1.hs.ch03.content` | high | 利用区间平移关系和定积分可加性化简积分，核心是一元函数定积分的性质与计算。 |
| 15 | `math1.la.ch11.content` | `math1.la.ch11.content` | high | 把向量的内积条件转写为线性方程组并求系数平方和，属于向量内积与线性表示。 |
| 16 | `math1.pr.ch17.content` | `math1.pr.ch17.content` | high | 结合独立性枚举两个离散随机变量取相同值的联合概率，属于二维随机变量及其联合分布。 |
| 17 | `math1.hs.ch08.content`, `math1.hs.ch03.content`, `math1.hs.ch02.content` | `math1.hs.ch08.content` | high | 第一问由几何条件建立并求解一阶微分方程；第二问结合原函数、导数判极值和定积分求最大值，涉及常微分方程、一元积分与微分。 |
| 18 | `math1.hs.ch05.content` | `math1.hs.ch05.content` | high | 求二元函数驻点并用二阶偏导判别极值，属于多元函数的极值与二阶微分。 |
| 19 | `math1.hs.ch06.content` | `math1.hs.ch06.content` | high | 将闭曲面积分转为区域上的三重积分，再用柱坐标计算，核心是多元函数积分及高斯公式。 |
| 20 | `math1.hs.ch02.content` | `math1.hs.ch02.content` | high | 用二阶泰勒公式的拉格朗日型余项构造中值点并给出不等式估计，属于一元函数微分学中的中值与泰勒定理。 |
| 21 | `math1.la.ch14.content` | `math1.la.ch14.content` | high | 通过配方和特征值比较讨论二次型的可逆变换标准形及正交变换可能性，直接对应二次型。 |
| 22 | `math1.pr.ch17.content`, `math1.pr.ch18.content` | `math1.pr.ch17.content` | high | 前两问使用二维密度的对称性、协方差和独立性，第三问用极坐标求平方和的分布，涉及二维分布与数字特征。 |

## 完整性校验

- entries 数量：22（要求 22）
- number：1..22 连续、无缺号、无重复。
- 节点合法性：通过；所有 nodes/primary_node 均来自当前 TSV，合法节点总数 66。
- confidence：high 21，medium 1，low 0。
- null：0；无题目被判定为疑似考纲外。
- JSON 输出：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\mapping\map-math1-2023-luna.json`
- 本报告：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\mapping\report-map-math1-2023-luna.md`
