# 2024 数学一映射报告（coder: claude）

## 基本信息

- 题干来源：
  - `F:\workspace\kaoyan-ai-system\data\raw_materials\math1\exam_papers\math1_2024_ztbu.pdf`（有文本层，5 页）
  - `F:\workspace\kaoyan-ai-system\data\raw_materials\math1\exam_papers\math1_2024_kmf.pdf`（有文本层，12 页，含详细解析）
  - 两份 PDF 均可用 `pypdf` 直接抽取文本（未用到 `pypdfium2` 渲染兜底）。
- 节点表：`math1_2024_nodes.tsv`，66 个节点（不含表头），与任务书描述的节点数一致。
  - 任务书给出的 sha256 `2c7d7dbbe194f5b1be701821a613b2dfb1cb4b7f265cd7de30d87ae02c942598` 为 65 位十六进制字符，长度不合法（正常 sha256 应为 64 位），怀疑任务书里的哈希值有笔误。
  - 实际计算得到的 sha256（`py -3.12` + `hashlib.sha256`）为：
    `8d9543368faf6fc8ebf45d8b548deffd59f15081253b94676788b95c0de56d82`
  - 由于节点数量（66）与任务书描述一致，且节点表内容本身可读、无异常，判断为可正常使用的同一份文件，仅哈希值记录有误，已如实在 JSON `meta.node_table_sha256` 中填写实际计算值。

## 方法

1. 用 `py -3.12` + `pypdf` 抽取两份 PDF 全部文本到 `extracted/*.txt`（UTF-8），逐题阅读题干与（kmf 版本的）详细解析。
2. 对照 `math1_2024_nodes.tsv` 中列出的 22 个二级章节（一~八 高数、一~六 线代、一~八 概率统计）的 `content` 节点，逐题判断考点归属。
3. 优先选择更细粒度的 `.content`（考试内容）节点；当一题明显跨两个章节的核心考点时，在 `nodes` 中列出全部相关节点，并指定其中最贴合的一个作为 `primary_node`。
4. 未发现任何题目在节点表中找不到合理归属（22 题均在数学一考纲范围内，无 `null`）。
5. 生成 JSON 后用脚本校验：`entries` 恰好 22 条、`number` 为 1~22 无缺无重、所有 `nodes`/`primary_node` 均在节点表 id 集合中、无非法自创 id。

## 逐题结果一览

| # | primary_node | confidence | 简述依据 |
|---|---|---|---|
| 1 | math1.hs.ch01.content | medium | 变限积分定义的函数奇偶性判断，概念在 ch01，手段（换元）在 ch03，跨章节 |
| 2 | math1.hs.ch06.content | high | 第二类曲面积分转二重积分 |
| 3 | math1.hs.ch07.content | high | 幂级数和函数反求系数并求和 |
| 4 | math1.hs.ch01.content | high | 极限存在性与连续性逻辑关系辨析 |
| 5 | math1.la.ch12.content | high | 系数矩阵/增广矩阵的秩判断线性方程组解的结构 |
| 6 | math1.la.ch11.content | high | 向量组线性相关性与秩 |
| 7 | math1.la.ch13.content | high | 特征值重数判定及矩阵幂的迹 |
| 8 | math1.pr.ch17.content | high | 独立正态变量线性组合的分布 |
| 9 | math1.pr.ch18.content | medium | 条件分布求联合密度后计算协方差，落点在数字特征 |
| 10 | math1.pr.ch17.content | high | 两随机变量函数的分布 |
| 11 | math1.hs.ch01.content | high | 待定参数的未定式极限 |
| 12 | math1.hs.ch05.content | high | 多元复合函数求导（链式法则） |
| 13 | math1.hs.ch07.content | high | 傅里叶（余弦）级数系数与极限 |
| 14 | math1.hs.ch08.content | high | 一阶微分方程初值问题 |
| 15 | math1.la.ch14.content | medium | 类柯西不等式型二次型不等式确定参数范围 |
| 16 | math1.pr.ch15.content | high | 条件概率 + 伯努利概型 |
| 17 | math1.hs.ch06.content | high | 二重积分计算（对称性/极坐标） |
| 18 | math1.hs.ch05.content | high | 切平面方程 + 闭区域最值 |
| 19 | math1.hs.ch02.content | medium | 泰勒中值定理证明不等式，第二问再积分 |
| 20 | math1.hs.ch06.content | high | 斯托克斯公式求第二类曲线积分 |
| 21 | math1.la.ch13.content | high | 递推数列矩阵化，特征值对角化求 n 次幂 |
| 22 | math1.pr.ch21.content | high | 无偏估计与均方误差最小的参数估计 |

完整字段（`nodes` / `reason` 等）见 JSON：
`map-math1-2024-claude.json`

## 统计

- 总题数：22（1~22 无缺无重）
- confidence：high 18 条，medium 4 条，low 0 条
- null（疑似考纲外）：0 条

## 纪律确认

- 未修改 `F:\workspace\kaoyan-ai-system` 下任何文件（仅只读抽取文本）。
- 未执行任何 git 命令。
- 全程使用 `py -3.12`；PDF 文本抽取结果先写入 UTF-8 文件（`extracted/*.txt`），再用 Read 工具读取，避免终端中文乱码。
- 独立完成，未参考或推测其他 coder 的产出。
