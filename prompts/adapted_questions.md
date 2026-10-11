# 改编复习题生成指引（M31）

输入包由 `ky planner-input --kind adapted-questions` 生成。按其中的知识点标题、树路径、
大纲条目和真题定位工作。输入包不包含真题题干；依据定位打开本机对应的真题 PDF，阅读原题，
再编写考查同一知识点、难度更低的新题。

要求：

1. 写 2–3 道题，题号按该知识点题库的下一个两位序号递增；每道题独立提交为一个 YAML 文件。
2. 不得复制真题题干，也不得只替换数字、名称或选项顺序。题目应明显更简单，同时考查同一知识点。
3. 每题提供答案和简要解析；选择题可以填写 `choices`，非选择题省略该字段。
4. 输入包有候选真题时，使用 `basis: past_questions`，并将所依据的候选 `question_id` 写进
   `based_on`。包内无候选时使用 `basis: syllabus` 和 `based_on: []`。
5. 固定 `difficulty: basic`、`validation: guided`，`created_by` 按 M19 actor 规则填写。
6. 将题目 YAML 写入本机 `staging/question_bank/`，保留输入包的完整 SHA-256 为 `input_hash`，
   然后由用户运行 `ky question-bank submit --from-staging FILE`。

示例字段形状：

```yaml
schema_version: 1
id: qb-math1.hs.ch02.requirements.item-03-01
knowledge_point_id: math1.hs.ch02.requirements.item-03
difficulty: basic
basis: past_questions
based_on: [math1-2025-01]
stem: "在这里写新的、更简单的题干。"
choices: ["A. 选项一", "B. 选项二"]
answer: "A"
explanation: "简要说明判断依据。"
validation: guided
created_by: ai:example-model
created_on: 2026-10-01
input_hash: <输入包的完整 SHA-256>
```
