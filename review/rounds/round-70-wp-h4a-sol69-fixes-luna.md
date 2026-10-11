# WP-H4a 第 70 轮修正报告

## 逐条落点

1. ky/knowledge/syllabus_mapping.py：新树 ID 覆盖现在区分显式目标、未变同名 ID 的隐式自环和 added；显式变更会抑制该 ID 的隐式自环。共同 ID 显式自指仍通过；无来源 ID 的错误包含该 ID。
2. 同文件：单条 changes[i].to 重复目标在 changes[i].to[j] 拒绝；跨变化共享目标仍允许合并。
3. 同文件：先用 workspace.require_all("reference.syllabus_versions.<subject>.mappings") 核实映射文件登记位置，再加载内容；版本树路径改为 workspace.require(...) 获取，越界 junction 会失败。
4. ky/workspace.py：同科不同版本标签若指向同一路径，在后一个标签的字段路径报错。contracts/workspace.md 说明大纲未变化时不应新增标签，并解释此约束使 effective_version() 不依赖 YAML 顺序。
5. SyllabusMapping 保留旧树 ID 集；targets() 对不属于源树的 ID 在 old_id 路径抛 ContractError。contracts/syllabus_mapping.md 同步说明。
6. 根和 changes[i] 的未知键均按 key=str 排序；混合类型键稳定转成带字段路径的 ContractError。
7. Workspace.require() 仅在该科映射列表确实登记时提示 use require_all；未登记科目返回 not registered。

## 撤检查变红记录

每项均在临时修改对应检查后运行精确用例，记录失败后立即还原：

- B1：停用零覆盖拒绝后，共同 ID 显式映射到空列表、显式映射到另一新增 ID 两个用例都因未抛 ContractError 变红；停用多重覆盖拒绝后，隐式自环同时有其他显式来源用例变红。
- B2：停用单条 to 去重后，重复目标用例未抛 ContractError，变红。
- B3：停用映射路径成员检查后，未登记映射路径用例未抛 ContractError，变红；临时改回直接读取版本路径后，越界 junction 用例未抛 ContractError，变红。junction 探针成功创建并运行。
- B4：停用同科版本路径唯一性检查后，重复路径用例未抛 ContractError，变红。
- B5：停用 targets() 的源树成员检查后，未知旧 ID 用例未抛 ContractError，变红。
- B6：根键和变化项未知键各自恢复普通 sorted() 后，对应混合整数/字符串键用例都抛原生 TypeError，变红。
- B7：临时恢复按键前后缀无条件分类后，ghost 科目的错误文案断言失败，确认被误报成 path list。

## 验收

指定命令：

    py -3.12 -m unittest tests.contract.test_syllabus_mapping_port tests.contract.test_workspace tests.test_verify_tree_shapes tests.contract.test_knowledge_tree_port tests.contract.test_subject_onboarding

结果：Ran 66 tests，OK (skipped=1)。跳过项是受权限限制的符号链接探针；本轮新增的目录 junction 越界探针实际执行并通过。

另在最终命令前对映射与 workspace 两模块做定向复测：Ran 37 tests，OK (skipped=1)。git diff --check 通过。变更文件未发现问号乱码串。

全量：未跑。不提交。
