# 复审：B′4 对照测试修复（dc1d04e，已合并 master 462e1d7）

只看你第 50 轮 T1/T3/T4 是否修好：`git show dc1d04e`。可单跑 `py -3.12 -m unittest tests.test_cs408_lecture_pipeline`（主工作区另有 H2 会话在改注册表，若该测试因注册表中间态失败请注明，不算本提交问题）。
复现你的删行探针。产物追加到 `review/rounds/round-50-review-sol-out.md` 末尾（"## 复审 dc1d04e"），给 PASS / FAIL。
