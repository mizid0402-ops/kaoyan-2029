# 数学一 2026 真题知识树映射报告

- coder: luna
- year: 2026
- subject: math1
- 节点表规范化 SHA-256: `2c7d7dbbe194f5b1be701821a613b2dfb1cb4b7f265cd7de30d87ae02c942598`
- 节点表原始字节 SHA-256: `8d9543368faf6fc8ebf45d8b548deffd59f15081253b94676788b95c0de56d82`

## 输入与核对

已只读完整核对以下两份题干来源：

- `F:\workspace\kaoyan-ai-system\data\raw_materials\math1\exam_papers\math1_2026_kaoyan.pdf`
- `F:\workspace\kaoyan-ai-system\data\raw_materials\math1\exam_papers\math1_2026_faiusr.pdf`

两份 PDF 均存在文本层；按题号交叉核对至第 22 题，未对源文件做任何修改。节点只取自 `tasks\math1_2026_nodes.tsv`。
任务书给出的 SHA-256 是规范化换行后的值；当前文件原始字节采用 CRLF，因此原始字节哈希不同，但将 CRLF 规范化为 LF 后与任务书给出的哈希一致。

## 映射摘要

| 题号 | primary_node | confidence | nodes 数 |
|---:|---|---|---:|
| 1 | `math1.hs.ch05.content` | high | 1 |
| 2 | `math1.hs.ch07.content` | high | 1 |
| 3 | `math1.hs.ch02.content` | high | 1 |
| 4 | `math1.hs.ch06.content` | high | 1 |
| 5 | `math1.la.ch10.content` | high | 1 |
| 6 | `math1.la.ch12.content` | high | 1 |
| 7 | `math1.la.ch14.content` | high | 2 |
| 8 | `math1.pr.ch18.content` | high | 1 |
| 9 | `math1.pr.ch18.content` | high | 2 |
| 10 | `math1.pr.ch16.content` | high | 1 |
| 11 | `math1.hs.ch06.content` | medium | 1 |
| 12 | `math1.hs.ch01.content` | high | 1 |
| 13 | `math1.hs.ch02.content` | high | 1 |
| 14 | `math1.hs.ch03.content` | high | 1 |
| 15 | `math1.la.ch13.content` | high | 1 |
| 16 | `math1.pr.ch18.content` | high | 2 |
| 17 | `math1.hs.ch05.content` | high | 1 |
| 18 | `math1.hs.ch08.content` | high | 2 |
| 19 | `math1.hs.ch06.content` | high | 1 |
| 20 | `math1.hs.ch02.content` | high | 1 |
| 21 | `math1.la.ch12.content` | medium | 3 |
| 22 | `math1.pr.ch21.content` | high | 3 |

## 结论

共编码 22 题；high 20 题、medium 2 题、low 0 题；null 0 题。没有发现需要标注“疑似考纲外”的题目。

详细依据与节点数组见同目录 JSON 文件。
