# 第 277 轮：M33 / M16 实现初检（sol61-m16）

结论：**FAIL**，5 项 MAJOR 必须改；范围仅任务书点名项，未展开全仓审计。
已读未提交 diff、M33/M16 实现、两份规格与第 276 轮报告；未联网、未读个人/忽略的学习状态。
只写本报告；探针均用合成数据与系统临时目录，没有启动真实工作区服务。

## 点名项核对

- 274 R1：显式 store/config/workspace 的支持及共享恢复管线已补；登记表缺省路径没有固化进恢复提示，C1 未关闭。
- 274 R2：阶段表合理，普通“新冻结→事件写入失败”能标 freeze_written；锁存后的读取失败及原生 IO 异常仍漏标，见 C2。
- submitted_review_ids 合理：outcomes 只装做过的项，新增集合校验包括 skip 的字段 ID；实现取两者并集，不会因漏传而绕过 outcomes 校验。
- 基线矩阵实际通过，但身份断言不具区分能力（C4）；网页缺题声明、HTML 转义、锁内按请求取今天、串行 POST 与表单 C 的路由静态符合修订规格。

## 必须改

### C1 / MAJOR：恢复提示没有带齐本次解析出的实际路径

位置：`ky/__main__.py:1561,1576,1594-1605`；`today.md` §4.1 要求实际 store/review-store/config 全部固定。
可复现输入：登记工作区下 record 省略 store/config，仅传 review-store；注入推进失败后查看提示。
本轮隔离探针输出只有 review-store/workspace，没有已解析的 plans/config 路径；函数明确只复制显式参数。
隐式发现注册表的调用还不带 workspace，换目录执行提示会重新寻找来源，无法保证恢复原事件与算法。
必须用本次已解析的 store/config/queue 路径构造命令，并保留显式 workspace；不要让恢复重新选择来源。

### C2 / MAJOR：已有冻结副作用仍被标 rejected，真实磁盘异常绕过阶段包装

位置：`ky/today/record.py:45-67,126-130`；M33 §4 阶段表。
可复现输入：合成积压超过阈值，真实 write_freeze_record 成功后，下一次 freeze_events 注入 StorageError。
本轮探针结果：`stage=rejected`、冻结事件 1 条、完成事件不存在；不能宣称 rejected 没有写入。
另据存储代码 `day_plan_store.py:183-189` / `review_shards.py:772-793`，写文件可直接抛 OSError；本管线相应 catch 不接它，会漏掉部分失败页/恢复提示。
必须保存已发布阶段并传播；锁存后不要靠重新读文件才能交回“已写”标记；正常 IO 失败也按已持久化阶段包装。

### C3 / MAJOR：真题元数据被当成题面，页面看不到题号

位置：`ky/web/server.py:149-159`；`ky/today/questions.py` 返回真题时同时提供 question 与 question_ref。
可复现输入：question_level=past_question、question_ref=probe-subject-2026-01，question 为含 question_id/exam_year/number/locator 的非空映射。
本轮渲染探针输出 `PAST_QUESTION_REF_VISIBLE=False`、`EMPTY_PARAGRAPH=True`；真题没有 stem，首个分支拦住了题号分支。
必须按 question_level/check 区分真题与改编题；真题显示引用/年份题号，改编题才渲染题面选项，文字继续转义。

### C4 / MAJOR：基线身份断言同样接受新版源码

位置：`tests/contract/test_today_port.py:356-360,529-533`；AGENTS.md 12a。
可复现输入：把当前 `ky/__main__.py` 源码代入 identity 条件；矩阵检查的三个 def、失败对照检查的两个 def 在新版仍全部存在（_preflight_calculate 留了包装函数）。
固定 git archive 确实取到 60a4fd2，本轮不是新版对新版；但该断言不能证明旧实现身份，不能当作此项验收已满足。
必须断言真正的旧实现特征（例如已删除的旧记录函数/旧函数体），并明确当前源码不满足；两个基线用例都要更新。

### C5 / MAJOR：装配函数仍超过 D7 的拆分界限

位置：`ky/today/port.py:71-148`；AGENTS.md D7 要求约 60 行以上拆有名字的辅助函数。
可复现输入：解析 ky/today/port.py 的 AST；本轮长度探针得到 `_load_today_context=78` 行。
该函数合并读取、预算/裁剪、出题、路线/课表/复盘/记录映射构造；应提取有名字的映射构造步骤，保持读取对象与字节输出。
AST 检查未发现 ky/today、ky/web 生产代码跨模块 import 私有名；其余函数没有超过 60 行。

## 留给最终大检查

- 矩阵覆盖 §6 点名的默认/显式、无注册表、usage、策略、冻结、出题两种输出；record 使用空 reviews，未证明非空队列推进分支的旧新字节一致。
- advance 省略 review-store 会选登记队列，record 省略则不推进；规格“完全相同”需明确这一默认行为差别，不能悄悄改变 record。
- 同一渲染探针发现 study_minutes=0 被显示成“未填写”；应区分 None 与 0，待最终检查修正。
- 出题计算仍通过 _ancestor_map/M24 读树与索引；来源一次读取及“计算层不暗读文件”的约束尚需最终核查；模块头公开接口列表也需补齐。
- 本轮未实际跑跨午夜/回退/失败页 HTTP 用例，仅审路由及现有测试；pending 页暂不列已存结果，手机宽度/深浅色仍待视觉检查。

## 安全登记与验证

- CSRF/认证、CLI 与网页并发、恶意链接沿用既有登记，不计当前 FAIL；转义探针确认 `x<0 & y` 按文本输出。
- 唯一 unittest：`py -3.12 -B -m unittest tests.contract.test_today_port.TodayPortContractTests.test_fixed_cli_baseline_matrix_matches_process_and_output_tree`，1 test / 30.140s / OK；另对点名项 1、4、5 各一条隔离探针。
- 全量未跑（按 AGENTS.md）；未提交，未修改实现或测试。
