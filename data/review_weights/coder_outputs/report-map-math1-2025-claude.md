# 2025 年数学一真题 → 考纲知识树映射报告（coder: claude）

## 基本信息

- 节点表：`tasks/math1_2025_nodes.tsv`（66 个节点）
- 节点表实际 sha256（本地计算）：`8d9543368faf6fc8ebf45d8b548deffd59f15081253b94676788b95c0de56d82`
  - 注意：任务书中给出的 sha256 `2c7d7dbbe194f5b1be701821a613b2dfb1cb4b7f265cd7de30d87ae02c942598` 长度为 65 个字符，不是合法的 sha256（应为 64 位十六进制），推测任务书中的哈希值有笔误。本报告及输出 JSON 中记录的是对当前 `math1_2025_nodes.tsv` 文件实际计算得到的 sha256，供比对。
- 题干来源：
  - `F:\workspace\kaoyan-ai-system\data\raw_materials\math1\exam_papers\math1_2025_kuaiyizhi.html`（主要来源，用 `py -3.12` + `bs4` 提取正文，并将 KaTeX 的 `<annotation encoding=application/x-tex>` 还原为 LaTeX 源码，避免逐符号拆分导致的公式失真）
  - `F:\workspace\kaoyan-ai-system\data\raw_materials\math1\exam_papers\math1_2025_ztbu.pdf`（用 `pypdfium2` 提取文本层，逐页与 HTML 版本交叉核对 22 题题干与解析，未发现实质性出入）
  - `math1_2025_juying.pdf` 未再单独提取，因前两个来源已互相印证一致。
- 未修改 `F:\workspace\kaoyan-ai-system` 下任何文件；未执行任何 git 命令。
- 中间产物（`extracted_html_text2.txt`、`ztbu_all.txt` 等）均以 UTF-8 写入后再用 Read 工具读取，避免终端吞中文。

## 映射结果概览

- entries：22 条，`number` 为 1～22，无缺无重（已用脚本校验）。
- confidence 分布：high 14 条，medium 8 条，low 0 条。
- null（疑似考纲外）：0 条，22 题均在给定节点表中找到对应章节。
- 所有 `nodes` / `primary_node` 均已校验存在于 `math1_2025_nodes.tsv` 的 66 个节点 id 中。

## 逐题要点（详见 JSON 中 reason 字段）

| 题号 | 主节点 | confidence | 一句话依据 |
|---|---|---|---|
| 1 | math1.hs.ch02.content | medium | 变限积分函数求导判断极值/拐点，微分学为主、积分学为辅 |
| 2 | math1.hs.ch07.content | high | 交错级数绝对/条件收敛判定 |
| 3 | math1.hs.ch02.content | medium | 反例法+洛必达法则判断极限存在性 |
| 4 | math1.hs.ch06.content | high | 二重积分交换积分次序 |
| 5 | math1.la.ch14.content | high | 二次型正惯性指数（借助特征值符号） |
| 6 | math1.la.ch12.content | medium | 由矩阵/增广矩阵秩判断方程组解集几何图形 |
| 7 | math1.la.ch10.content | medium | 矩阵乘积秩的等式/不等式关系反例 |
| 8 | math1.pr.ch18.content | medium | 方差/协方差公式求 D(aX+bY) 最大值 |
| 9 | math1.pr.ch16.content | high | 泊松定理近似二项分布 |
| 10 | math1.pr.ch22.content | high | 正态总体均值单侧检验拒绝域 |
| 11 | math1.hs.ch01.content | high | 未定式极限计算 |
| 12 | math1.hs.ch07.content | high | 傅里叶级数和函数（周期延拓）取值 |
| 13 | math1.hs.ch05.content | high | 方向导数计算 |
| 14 | math1.hs.ch06.content | high | 第二类曲线积分+格林公式 |
| 15 | math1.la.ch10.content | medium | 行列式为零判断 A²x=0 与 Ax=0 不同解 |
| 16 | math1.pr.ch15.content | high | 独立事件+条件概率计算 |
| 17 | math1.hs.ch03.content | high | 有理函数定积分（部分分式分解） |
| 18 | math1.hs.ch05.content | medium | 复合函数偏导化简为常微分方程再求解 |
| 19 | math1.hs.ch02.content | high | 拉格朗日中值定理证明单调性充要条件 |
| 20 | math1.hs.ch06.content | high | 第二类曲面积分+高斯公式（旋转曲面） |
| 21 | math1.la.ch13.content | high | 特征值重根+广义特征向量方程 |
| 22 | math1.pr.ch16.content | medium | 随机变量函数分布+全概率公式求复合分布 |

## 需要说明的低把握 / 跨章节题目

- 第 1、3、18 题：一元函数微分学与积分学/常微分方程交叉，按“主要求解技巧所在章节”定为主节点，medium。
- 第 6、7、15 题：线性代数中矩阵的秩、线性方程组、向量三章内容高度关联，本题组按“最终结论所属章节”取主节点，medium。
- 第 8、22 题：概率论中随机变量分布与数字特征常同时出现，按“题目直接设问的对象”取主节点，medium。

全部 22 题均已给出节点映射，无 null 项。
