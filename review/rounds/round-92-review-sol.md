# 复审：`b120c71`（你第 90 轮 WP-E1 的 C1 / C2 与 W2）

遵守 `AGENTS.md`（不跑全量）。运行用 `git archive b120c71`（原始资料与 `products` 空目录照你上一轮做法补）。另有 luna 在主工作区做 WP-E2，与本次无关，不用看。

只看 `git show b120c71`：C1（经 junction 读到工作区外的缺省队列）、C2（缺省队列登记成文件）原复现是否关闭；`_registered_queue_path` 用于 `review-queue` 后有无行为变化；W2 表驱动测试是否恰当；新测试撤修复是否变红。C4 的 `--review-store` 回归测试建议本轮未做（可反驳）。

产物：`review/rounds/round-92-review-sol-out.md`，每项"必须改 / 建议改 / 不改"附可复现输入，最后 PASS / FAIL。只写这一个文件。
