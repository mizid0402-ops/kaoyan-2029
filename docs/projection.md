# 本机只读 Web 投影

投影是根据工作区注册表登记的知识树、补充视图、真题索引、题目权重和词库依赖生成的 SQLite 派生视图，不是真相源。字段、表结构（schema version 2）、输入哈希、生效/补充分离与只读约束见[投影契约](../contracts/projection.md)。

在仓库根目录重建：

```powershell
py -3.12 -m ky.projection
```

注册表按 `--workspace`、`KY_WORKSPACE`、向上查找的顺序发现；指定位置或覆盖输出：

```powershell
py -3.12 -m ky.projection --workspace path/to/kaoyan.workspace.yaml --out path/to/projection.sqlite
```

默认写入注册表的 `projection` 路径。缺少任一登记输入时命令以 exit 2 报告契约违约，旧投影保持不变。生成器先在目标旁建立临时数据库，再原子替换目标。

启动本机只读服务：

```powershell
py -3.12 -m ky.projection.serve
```

服务默认读取注册表的 `projection` 路径，可通过 `--workspace` 指定注册表，或通过 `--database` 显式覆盖；Datasette 始终以 `--immutable` 模式运行：

```powershell
py -3.12 -m ky.projection.serve --workspace path/to/kaoyan.workspace.yaml --port 8010
```

自动化黑盒测试会配置一个确定可执行的写查询，再通过 HTTP `POST` 调用。服务必须返回 `403` 和 `Database is immutable`，随后检查 SQLite 值未变化：

```powershell
py -3.12 -m unittest tests.test_projection_service -v
```

## Windows 文件占用

重建前先停止正在运行的 Datasette 服务。Windows 可能在服务持有数据库句柄时拒绝原子替换；此时构建器保留旧投影并说明停止服务后重建。
