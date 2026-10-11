# 第 279 轮：M33 / M16 实现复审初检（sol61-m16）

结论：**FAIL**。C1–C5 的原问题已修；C5 拆分直接引入 1 项 MAJOR 日常回归（N1）。
只核对原问题、带复习项的新基线分支与返工直接影响；不展开旧的最终检查事项。
本轮只写本报告；未联网、未读取个人/忽略的学习状态、未启动真实工作区服务。

## C1–C5 关闭情况

- C1 已关闭：CLI 传入实际 store_path、review_store.root、config_path、workspace.source；登记/发现路径也进入提示，恢复不再重新发现注册表（`ky/__main__.py:1561-1605`，静态核对）。
- C2 已关闭：冻结发布后直接 replace(status, latched=True)，不再重读冻结文件；完成写入/推进捕获 OSError 并保留 rejected/event_written 阶段；相关单个用例通过。
- C3 已关闭：按 question_level/check 区分真题与改编题，真题输出引用及年份题号；新增渲染用例通过，转义仍统一走 _esc。
- C4 已关闭：旧版独有的冻结/推进函数作为身份依据，并排除当前源码；两个基线用例都补了旧实现特征检查，固定 archive 仍为 60a4fd2。
- C5 原长度问题已关闭：装配与映射构造拆开，AST 扫描 M33/M16 没有函数超过 60 行；但课表 helper 丢失 None 分支，见 N1。
- 附带显示修订已核对：配额采用中文名、周期终日及次日复盘、0 分钟保留；advance 缺省 review-store 的例外已写进 §4.1。

## 新基线分支是否真的比较推进后文件树

`test_today_port.py:479-485,547-583` 使用非空 review-event，并显式给出 review-store。
旧/新都重置相同种子，在同一路径运行；进程结束后 output_tree(runtime) 进入 compare_runs 的原始字节比较。
本轮只在内存中加观察包装，保留原 compare_runs：新增分支退出 0，stdout 为 advanced: 1 completion(s)，manifest 含 `2026-09-15#0`。
因此已确认比较的是完成事件和队列推进后的完整文件树，不是仅比较输入树或两个均失败的结果。
单个固定基线矩阵：1 test / 29.001s / OK；原基线身份与字节比较未被观察包装替换。

## 仍需改

### N1 / MAJOR：登记课表存在、日期在学期外时，今日视图崩溃

位置：`ky/today/port.py:146-152`；`contracts/today.md:52-53` 明定学期外 timetable 为 null。
可复现输入：正常登记课表，查看一个不在任何已登记学期内的日子（例如寒暑假或只读查看未来日期）。
M18 `calendar.py:152-162` 合法返回 None；新 helper 只判断 timetable 对象是否为 None，随后直接访问 schedule.semester。
本轮唯一探针：临时合成工作区，M18 provider 按此契约返回 None，调用 load_today；结果 `AttributeError: 'NoneType' object has no attribute 'semester'`。
网页对应 GET 会变成 500，record_day 也无法装配视图；拆分前已有 schedule is None 的保护，属于返工直接回归。
必须在 timetable.day(...) 返回 None 时直接映射为 null，并覆盖“已登记课表、学期外”这一条回归输入。

## 留给最终大检查

- 显式相对路径仍按原参数进入恢复提示；跨目录复制命令需保持原 cwd，若要求跨目录恢复应固定为绝对路径。
- pending 页展示已存结果、来源一次读取、模块头公开接口列表及手机宽度/深浅色仍沿用第 277 轮待查项，本轮未扩审。
- 发布后的临时文件清理失败等存储层阶段信号与安全登记留最终检查；本轮不新增安全返工项。

验证：各跑 1 个基线矩阵、OSError 阶段用例、网页显示用例，均 OK；C5 仅一条 AST/学期外联合探针。
未跑全量，未修改实现或测试，未提交；以上 PASS 用例不构成对 N1 的豁免。
