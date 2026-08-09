**语言：** [English](../../orchestration/viewer.md) | **简体中文**

# 本地编排 Viewer

Viewer 在不引入第二个状态所有者的前提下，为人类提供受管运行树查看能力。[`xc-orchestration-viewer`](../../../skills/xc-orchestration-viewer/SKILL.md) 是无脚本 facade；[`xc-orchestration-runtime`](../../../skills/xc-orchestration-runtime/SKILL.md) 负责快照、server、registry、SVG 渲染和静态前端资产。

这种单向依赖可以避免 runtime 与第二套可视化实现在 schema 和状态语义上发生漂移。

## 快照边界

Viewer 从不解析或编辑受管 runtime XML。Runtime 的 `snapshot` 操作生成供 server 和浏览器消费的稳定只读 JSON 模型，其中包含 runtime metadata、节点层级、状态统计、blackboard 值、ready 节点、完整性信息和版本。

Server 为每个注册运行树保留最近一次有效快照。如果刷新时源暂时缺失或无效，UI 可以继续展示最近有效数据，同时报告健康状态和当前错误。

Viewer API 包含 registry、snapshot、refresh、SVG download、client、heartbeat 和 native picker 操作，不提供 `start`、`complete`、`fail`、`block`、`set` 或其他编排修改操作。

## 启动与默认值

启动 runtime 所有的 server：

```powershell
python <runtime-skill-dir>/scripts/viewer_server.py --tree <tree-ref>
```

Server 只绑定 `127.0.0.1`，首选默认端口为 `20668`；端口被占用时使用可用的
临时端口。默认值来自最近的 `.xcoding/xc-orchestration-runtime.json`，
runtime 随附的 JSON 配置是参考：

```text
watch interval: 1 秒
heartbeat: 15 秒
idle shutdown: 120 秒
```

默认启动模式创建 detached background process、打开浏览器，并返回一个包含 `ok`、`mode`、`pid`、`url` 和 `trees` 的 JSON 结果。Background 模式不写日志。`--foreground` 让 server 留在当前终端，并输出 JSON-line lifecycle、client 和 refresh 事件。`--no-browser` 用于自动化验证。

本地 Viewer server 是查看工具，不是编排 daemon 或远程 runtime API。

## Viewer 与 Package Daemon

Prerelease package 的 `xc daemon serve` 是独立的本地工具 API。它默认使用端口
`20669`，要求 process-lifetime bearer token 和精确 Host/Origin 检查，只接受
启动时传入的 runtime 文件，暴露九个 typed read-only query，并提供有界、不可
replay 的 summary SSE。

Viewer 继续作为端口 `20668` 上的 browser interface，拥有自己的 UI、Viewer
本地 registry、refresh control、native picker 和 SVG download。两者不共享
daemon token 或 registry。原生 browser `EventSource` 不能提供 daemon bearer
header，也不是 daemon 的目标客户端。两个 server 都不暴露 orchestration
mutation、remote bind、durable event log、discovery 或 auto-start。

## Registry 与刷新

可重复使用 `--tree` 注册初始运行树。显式 tree path 自动获准；后续直接路径注册仅限通过 `--allow-root` 提供的目录。

Server 按配置间隔监视已注册源。浏览器每 20 秒检查一次选中快照，只有版本变化时才重新渲染；同时保留手动强制刷新。

每个浏览器页面拥有独立 client 注册和 heartbeat。没有 active client 达到配置 idle 时间后，server 会自动关闭，background 模式也一样。需要诊断生命周期时可使用 foreground 模式。

## Native Picker 安全

Native picker 刻意比任意本地文件访问更严格：

- 请求必须使用 server 实际绑定的 loopback Host。
- 浏览器提供 Origin 时，必须与 Viewer origin 匹配。
- Picker 请求串行执行；一个 dialog 活跃时拒绝第二个请求。
- Dialog 在 helper process 中运行，并由该进程主线程拥有 UI。
- Windows 上 helper 不打开 console window。
- 用户取消属于正常结果。
- 选择一个有效 runtime 文件只授权该文件的父目录。

直接路径注册不会扩大 allow roots。Server 不绑定局域网或公网接口，也没有远程认证模型。

## 用户界面

静态 HTML、CSS 和浏览器 JavaScript 渲染连线的水平树。实现使用自定义浏览器代码，不依赖 D3。

界面提供：

- 可折叠 sidebar，用于注册、选择和移除 Viewer 本地实例。
- 节点状态、executor、role、时间、结果、artifact 和详情。
- Blackboard key/value 行和 runtime 更新时间。
- 每棵树独立的折叠状态、平移、滚轮缩放和同步 range-slider 缩放。
- 可通过指针和键盘调整的高尺寸图形 viewport。
- 手动刷新、连接状态、健康报告和自动重连。
- 完整独立 SVG 下载。

移除实例只影响 Viewer registry。浏览器中的折叠、平移、缩放和 viewport 状态绝不修改运行树。SVG download 包含完整快照，即使浏览器中有节点处于折叠状态。

## 操作边界

Viewer 用于理解进度和健康状态。任何状态转换、完整性修复、恢复或 artifact 查询都使用 runtime 公开命令。

Viewer 不提供 worker 管理、强制取消、历史 event sourcing、任意文件系统浏览或可写工作流 dashboard。这些不是隐藏 UI 功能，而是当前契约范围之外的能力。
