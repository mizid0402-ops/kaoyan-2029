# 2023 数学一试题 → 考纲知识树映射报告（coder: claude）

## 基本信息

- 题干来源：`F:\workspace\kaoyan-ai-system\data\raw_materials\math1\exam_papers\math1_2023_qihang.pdf`（只读，未修改）
- 节点表：`math1_2023_nodes.tsv`，共 66 个节点，实际 sha256（本地计算）：
  `8d9543368faf6fc8ebf45d8b548deffd59f15081253b94676788b95c0de56d82`
  （与任务书中给出的哈希字符串长度不一致，怀疑任务书中该值有笔误；已在 JSON 的 `meta.node_table_sha256` 中记录本地实际计算值，供核对。）
- 提取方式：PDF 有文本层，用 `py -3.12` + `pypdf` 直接抽取文本（公式经 OCR/PDF 转换后有轻微乱码，但结合上下文和已给出的【答案】【解析】可准确判断每题考点），写入 UTF-8 中间文件后阅读，未使用图像渲染。
- 输出 JSON：`map-math1-2023-claude.json`（同目录）。
- entries 数：22 条，number 1–22 无缺无重（已用脚本校验）。
- confidence 分布：high 19 / medium 3 / low 0。
- null 节点：0 条（22 题均在考纲节点表内找到对应节点，未发现疑似考纲外的题目）。

## 逐题要点（简要，非题干摘抄）

| # | 主要考点 | 主节点 | confidence |
|---|---|---|---|
| 1 | 曲线斜渐近线（极限求斜率与截距） | ch02.content | high |
| 2 | 二阶常系数齐次线性微分方程解的有界性 | ch08.content | high |
| 3 | 参数方程确定的函数，分段可导性/连续性判定 | ch02.content | high |
| 4 | 两收敛级数下绝对收敛的充要关系 | ch07.content | high |
| 5 | 分块矩阵秩的比较（初等变换） | ch10.content | high |
| 6 | 矩阵可相似对角化的判定 | ch13.content | high |
| 7 | 向量既可由一组基线性表示又可由另一组表示 | ch11.content | medium |
| 8 | 泊松分布下随机变量函数的期望 | ch18.content | high |
| 9 | 两正态样本方差比的 F 分布构造 | ch20.content | high |
| 10 | 无偏估计中待定系数的求法 | ch21.content | high |
| 11 | 等价无穷小比较求参数 | ch01.content | high |
| 12 | 隐函数曲面在指定点的切平面 | ch05.content | high |
| 13 | 周期函数傅里叶系数及其平方级数和 | ch07.content | high |
| 14 | 积分区间可加性+换元求定积分值 | ch03.content | high |
| 15 | 向量组正交内积关系求参数平方和 | ch11.content | high |
| 16 | 两独立二项分布变量的 P(X=Y) | ch17.content | high |
| 17 | 一阶线性微分方程求解 + 变限积分函数最值 | ch08.content（+ch03.content） | medium |
| 18 | 二元函数极值（偏导判别式） | ch05.content | high |
| 19 | 高斯公式计算曲面积分 | ch06.content | high |
| 20 | 泰勒公式+介值定理证明中值点存在 | ch02.content | high |
| 21 | 二次型化标准形（配方法+正交变换） | ch14.content | high |
| 22 | 二维随机变量：协方差/独立性/和的密度 | ch17.content（+ch18.content） | medium |

## medium/low 说明

- **第 7 题**：β 既可由 {α1,α2} 又可由 {β1,β2} 线性表示，核心概念是"向量的线性表示"（归入"三、向量"ch11），但求解过程需联立齐次线性方程组，与"四、线性方程组"存在交叉，故未标 high。
- **第 17 题**：分两问，第(1)问求解一阶线性微分方程（常微分方程 ch08），第(2)问求变上限积分函数 f(x)=∫₁ˣy(t)dt 在 (0,+∞) 上的最大值（涉及一元函数积分学 ch03 的应用）。因跨两章，主节点选取权重更大的 ch08，同时在 nodes 中保留 ch03，confidence 标为 medium。
- **第 22 题**：三小问分别对应"求协方差"（数字特征 ch18）与"判断独立性""求 Z=X+Y 密度"（多维随机变量及其分布 ch17）。按小问数量占比，主节点定为 ch17，同时保留 ch18，confidence 标为 medium。

其余 19 题的考点与知识树节点对应关系清晰、单一，故标为 high；本次映射未出现 low 置信度或考纲外（null）的题目。

## 纪律遵守说明

- 未修改 `F:\workspace\kaoyan-ai-system` 下任何文件（仅只读抽取 PDF 文本）。
- 未执行任何 git 命令。
- 全程使用 `py -3.12` 执行 Python 脚本；PDF 文本抽取结果与最终 JSON 均以 UTF-8 编码写入文件后再读取核对，避免终端中文乱码影响判断。
- 独立完成映射，未查看或参考其他 coder 的产出。
