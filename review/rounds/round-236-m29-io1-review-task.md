# 第 236 轮任务书：WP-IO1 实现评审（gpt-6.1-sol，续 sol61-m18）

## 范围

主工作区未提交的 IO1 改动（实现者报告 `review/rounds/round-228-m29-io1-luna.md`）：`ky/timetable/`（M18 公开入口与重构）、`ky/timetable_io/`（新，M29 隔离检查、暂存、`restage`、`apply`）、
`ky/__main__.py`（两个新子命令）、`contracts/timetable.md`、`tests/contract/test_timetable_port.py`、`tests/contract/test_timetable_io_port.py`。
用 `git diff` / `git status` 看改动。另外两个 worktree（`../kaoyan-wt-m28a`、`../kaoyan-wt-m28b`）里的 M28 工作不在本轮范围。

## 请判断

1. 是否符合 `contracts/timetable_import.md` §1、§2、§3、§5（逐条对照：三种隔离状态与每个写入路径、暂存封闭字段与 `hash12`、只写一次发布、`restage` 两种结果、
   `apply` 先完整校验再判"已应用"、备份与替换顺序和中断状态、退出码）。
2. M18 重构：`timetable_for_workspace` 的结果、`sources`、错误字段路径与读取次数是否与固定提交 `4816a14` 一致（看对照测试是否真的固定该哈希并断言取到旧版）；
   六个公开入口的校验范围是否与规格 §2 表一致；序列化形状。
3. `AGENTS.md` 已知缺陷清单逐条与 D7 可读性（模块头、函数长度、不 import 其他模块私有名）。
4. 测试是否覆盖任务书 `review/rounds/round-228-m29-io1-task.md` 列出的用例，有没有用例只断言了"能跑"而没断言结果。
5. 个人数据：被跟踪的文件与测试里不得出现用户的学校、课表内容；只报位置，不复述。

## 可以运行

只跑与结论直接相关的单个模块或单条命令；不跑全量。

## 输出

`review/rounds/round-236-m29-io1-review-sol61.md`：PASS / FAIL；必须改（附可复现输入与命令）/ 建议改 / 不改；安全登记单列。

## 禁止

不联网；只写这一份报告；不修改其他文件；不读仓库外文件；报告里不写个人数据。
