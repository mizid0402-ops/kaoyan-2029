# 评审任务书：第 198 轮 —— 新版来源固定（你第 197 轮 M2，窗口 `sol61-main`）

请复审 `luna-c` 第 198 轮。任务书 `review/rounds/round-198-d11-probe-root-fix-task.md`，报告 `review/rounds/round-198-d11-probe-root-fix-luna.md`。
范围：`tests/contract/test_freeze_scheduled_backlog.py` 相对你第 197 轮所见版本的变化；并确认其它文件与第 197 轮一致。

## 重点看

1. 用你第 197 轮的复现（临时副本积压 `+1`，同时设 `D11_PROBE_NEW_ROOT` 指向旧树）确认现在失败而不是 OK。
2. 新增的来源断言（`ky.__file__` 所在目录等于传入 checkout）是否对新旧两侧都生效，错配时确实失败。
3. 实现者把 CLI 改成经 `runpy` 启动 `ky.__main__`：旧版与新版是否用**同一种**启动方式；这会不会改变被比较的 stdout / stderr 字节，
   或让对照不再代表用户实际运行的 `py -m ky …`（例如 `sys.argv[0]`、`__spec__`、退出码传递的差异）。
4. 第 197 轮已确认的其它修正未被改坏。

## 规则

只跑与结论直接相关的单个模块或单条命令，**不跑全量**；复现用系统临时目录。结论 PASS / FAIL，分"必须改 / 建议改 / 不改"。

## 报告

`review/rounds/round-199-d11-probe-root-review-sol61.md`。
