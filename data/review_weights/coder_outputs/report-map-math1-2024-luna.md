# 2024 数学一试题映射报告（luna）

- coder：`luna`
- year：`2024`
- subject：`math1`
- started_at：`2026-09-13T19:54:56+08:00`
- 节点表 SHA-256（按 UTF-8 文本内容计算，与任务书口径一致）：`2c7d7dbbe194f5b1be701821a613b2dfb1cb4b7f265cd7de30d87ae02c942598`
- 节点表原始字节 SHA-256：`8d9543368faf6fc8ebf45d8b548deffd59f15081253b94676788b95c0de56d82`（当前文件为 CRLF，故与文本内容哈希不同）

## 输入核验

独立读取并交叉核对以下只读题源：

- `F:\workspace\kaoyan-ai-system\data\raw_materials\math1\exam_papers\math1_2024_ztbu.pdf`（5 页，含题目与答案）
- `F:\workspace\kaoyan-ai-system\data\raw_materials\math1\exam_papers\math1_2024_kmf.pdf`（12 页，含题目、答案与解析）

两份题源的题号均覆盖 1--22；映射依据为题目实际使用的数学对象、定理和计算方法，不依赖其他 coder 产出。

## 映射明细

| 题号 | 节点 | 主节点 | confidence | 判断依据 |
|---:|---|---|---|---|
| 1 | `math1.hs.ch03.chapter` | `math1.hs.ch03.chapter` | high | 变上限积分的奇偶性由被积函数的对称性决定，核心属于一元函数积分学。 |
| 2 | `math1.hs.ch06.chapter` | `math1.hs.ch06.chapter` | high | 第二类曲面积分通过曲面投影和法向方向换元，属于多元函数积分学。 |
| 3 | `math1.hs.ch07.chapter` | `math1.hs.ch07.chapter` | high | 由幂级数和函数反求带权系数和，使用逐项求导等幂级数方法。 |
| 4 | `math1.hs.ch02.chapter` | `math1.hs.ch02.chapter` | high | 判断函数值极限与一点导数之间的蕴含关系，依据是导数定义和连续性。 |
| 5 | `math1.hs.ch04.chapter` | `math1.hs.ch04.chapter` | medium | 平面的位置关系转化为法向量组及增广向量组的秩关系，属于空间解析几何。 |
| 6 | `math1.la.ch11.chapter` | `math1.la.ch11.chapter` | high | 参数由三向量的秩为二且任意两向量独立确定，直接考查向量组的线性相关性。 |
| 7 | `math1.la.ch13.chapter` | `math1.la.ch13.chapter` | high | 秩条件和特征向量条件先确定特征值及其重数，再计算矩阵幂的迹。 |
| 8 | `math1.pr.ch16.chapter` | `math1.pr.ch16.chapter` | high | 独立正态变量的线性组合仍为正态分布，比较标准化后的分布函数即可确定参数。 |
| 9 | `math1.pr.ch17.chapter`, `math1.pr.ch18.chapter` | `math1.pr.ch18.chapter` | high | 先由条件均匀分布构造联合密度，再用联合矩求协方差；分布建模与数字特征均被使用。 |
| 10 | `math1.pr.ch16.chapter` | `math1.pr.ch16.chapter` | high | 独立指数变量差的绝对值通过分布函数可化为同参数指数分布，核心是随机变量分布变换。 |
| 11 | `math1.hs.ch01.chapter` | `math1.hs.ch01.chapter` | high | 利用对数化和等价无穷小处理含参数的极限，属于函数极限。 |
| 12 | `math1.hs.ch05.chapter` | `math1.hs.ch05.chapter` | high | 复合函数的二阶导数由多元链式法则展开，并代入给定的一阶偏导信息。 |
| 13 | null | null | low | 需要傅里叶余弦级数展开及其系数渐近关系；节点表没有对应的傅里叶级数节点，疑似考纲外。 |
| 14 | `math1.hs.ch08.chapter` | `math1.hs.ch08.chapter` | high | 令因变量与自变量之和为新变量后可分离变量积分，属于一阶常微分方程。 |
| 15 | `math1.la.ch14.chapter` | `math1.la.ch14.chapter` | high | 对任意两组向量的双线性表达式施加平方不等式，等价于二次型的半负定条件。 |
| 16 | `math1.pr.ch15.chapter` | `math1.pr.ch15.chapter` | high | 三次独立重复试验的条件概率由互斥事件概率计算，属于随机事件和概率。 |
| 17 | `math1.hs.ch06.chapter` | `math1.hs.ch06.chapter` | high | 按平面对称性化简二重积分并完成区域上的积分计算，属于多元函数积分学。 |
| 18 | `math1.hs.ch05.chapter` | `math1.hs.ch05.chapter` | high | 先求曲面切平面，再在三角形投影区域内比较内部驻点、边界驻点和顶点值。 |
| 19 | `math1.hs.ch02.chapter`, `math1.hs.ch03.chapter` | `math1.hs.ch02.chapter` | high | 前半用二阶泰勒公式消去一阶项得到点态不等式，后半对不等式积分；微分学为主并连接积分学。 |
| 20 | `math1.hs.ch06.chapter` | `math1.hs.ch06.chapter` | high | 用斯托克斯公式把闭曲线积分化为平面上的曲面积分，再处理投影圆域。 |
| 21 | `math1.la.ch13.chapter`, `math1.la.ch10.chapter` | `math1.la.ch13.chapter` | high | 递推关系写成矩阵幂后用特征值分解求显式表达式，同时涉及矩阵运算。 |
| 22 | `math1.pr.ch21.chapter`, `math1.pr.ch20.chapter` | `math1.pr.ch21.chapter` | high | 样本最大值的分布用于构造无偏估计，并以均方误差最小化确定估计系数；兼涉次序统计量。 |

## 结果统计

- 条目数：22；题号集合：1--22，无缺号、无重复。
- confidence：high 20，medium 1，low 1。
- null 节点：1（第 13 题）。
- 第 13 题使用傅里叶余弦级数，而节点表未提供对应节点，按任务书要求填 `null`，并标注“疑似考纲外”。

## 输出文件

- JSON：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\mapping\map-math1-2024-luna.json`
- 报告：`C:\Users\Lenovo\AppData\Local\Temp\kaoyan-probe\mapping\report-map-math1-2024-luna.md`
