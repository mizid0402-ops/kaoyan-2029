# 任务书：WP-H5 收尾——拆分过长函数（D7）

决策者已审第 78 轮，实现与复现都通过。只剩一处可读性：`ky/exam/topic_weights.py` 的 `aggregate_topic_weights` 105 行、`_read_entries` 62 行（D7：约 60 行以内，一个函数一件事）。

把 `aggregate_topic_weights` 拆成有名字的步骤（例如：读清单与校验批次唯一、逐批读产出并投票、逐题归一化与舍入、上卷与累加 `topic_weight`、组装输出），公开函数只做编排；`_read_entries` 顺手压到 60 行内。
**行为不变**：浮点累加顺序不得改变。

验收（只跑这些）：

```
py -3.12 tools/aggregate_topic_weights.py --check
py -3.12 -m unittest tests.contract.test_topic_weights_port
```

报告写 `review/rounds/round-79-wp-h5-split-luna.md`（几行即可：拆成了哪些函数、两条验收输出）。全量：未跑。不提交。
