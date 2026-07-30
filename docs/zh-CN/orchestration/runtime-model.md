**语言：** [English (英文)](../../orchestration/runtime-model.md) | **简体中文 (Simplified Chinese)**

# 运行时模型

[`xc-orchestration-runtime` 契约](../../../skills/xc-orchestration-runtime/SKILL.md)定义了管理 `schema_version="1"` 运行树的领域中立控制面。Agent 只能通过公开命令操作它。

## 对象与身份

模板定义可复用结构。运行树是某个 work order 的实例，包含节点状态、blackboard 值、结果、已声明 artifact、循环历史、来源、revision、完整性和 sealing 元数据。

模板节点使用稳定的 kebab-case `template_id`。模板内依赖使用 `local:<template_id>`，实例化时重写为：

```text
rt_<work_order_id>__<instance_id>__<template_id>
```

每个实例化节点保留 `origin_template_id` 和 `origin_instance_id`。动态调用方提供 kebab-case `logical_key`，真实 ID 由 runtime 生成，其偶然拼写不是调用方契约。

嵌入模板拥有隔离的 instance namespace，并重写本地引用；它与父树共享 blackboard。当前不支持 blackboard 作用域转换、关联子 work order 或跨进程取消。

## 节点与状态

四种节点类型是：

- `composite`：sequence、parallel、switch 或 dynamic group。
- `task`：可执行叶子节点。
- `gate`：由 `executor=main` 处理的可执行叶子节点。
- `loop`：在轮次结束时判断的有界容器。

Executor 包括 `main`、`subagent`、`tool` 和 `service`。Runtime 根据 `type`、`mode`、`executor`、`when` 和依赖等控制字段执行；领域含义属于 `role`、`metadata.*` 和节点正文。

状态包括 `pending`、`ready`、`running`、`succeeded`、`failed`、`blocked` 和 `skipped`。`ready` 是合法状态，但主要由调度器计算。只有 task 和 gate 叶子可以启动或接收终态更新；`complete`、`fail`、`block` 要求节点为 `running`，`unblock` 把 blocked 叶子恢复为 pending。Composite 和 loop 状态由 runtime 计算。

`succeeded` 和 `skipped` 都满足流程推进条件。failed 或 blocked 后代会停止其所在 sequence，直到工作流显式处理。系统没有通用 `failed -> pending` retry 命令或自动重试政策。

## 调度与就绪

`next` 稳定化运行树并返回 ready 可执行叶子，可限制批量数量。`start` 使用同一 readiness 谓词；仅知道 ID 不能绕过节点状态、条件、依赖、祖先状态或 sequence 顺序。

- Sequence 只暴露第一个未完成且可达的子节点。
- Parallel composite 可以暴露多个相互独立的子节点。
- 显式依赖必须 succeeded 或 skipped。
- 条件只支持 truthy key、`!key`、相等和不等。
- `when.policy=reactive` 是默认值，条件值变化后可以重新打开条件性 skipped 节点。
- `when.policy=latched` 使该 skip 对当前模板实例保持最终状态。

Runtime 反复执行条件和 switch 路由以及自底向上的容器聚合，直至状态稳定。

## Switch

`mode=switch` composite 读取 `switch.key`。必须选择唯一匹配的 `role=case` 子节点或 default 子节点，其他分支进入 skipped。多个匹配会失败；无匹配默认失败，也可配置为 blocked。

复杂决策应由前置 task 计算并写入一个简短 blackboard 值。Switch 只路由该值，不提供通用表达式语言。

## 动态组与依赖

`role=dynamic-group` composite 默认开放，除非模板明确关闭。开放期间可通过 `add-node` 和 `embed-subtree` 添加工作。可达的空开放组会出现在 `awaiting_dynamic_groups` 中；orchestrator 必须添加工作或调用 `close-group`。空的关闭组会成功。

关闭组拒绝普通添加。`reopen-group --reason` 是可审计的恢复操作，获批恢复工作可用 `add-node --before` 插入。这是受控恢复，不是通用 retry。

显式依赖允许有限的跨树边，但模型仍以树为主。Author 不应借此构造难以理解的通用 DAG。

## 循环

每个 loop 都必须有正整数 `loop.max_iterations`，以及取值为 `failed`、`blocked` 或 `succeeded` 的 `loop.on_limit`。所有子节点 succeeded 或 skipped 后，runtime 求值 `loop.break_when` 和 `loop.continue_when`，记录轮次历史，然后退出、重置进入下一轮，或应用上限结果。

循环只在轮次边界决策。系统没有 `break-loop`、`continue-loop`、取消同级节点、终止子树、提前完成父节点或中止整次运行等控制信号。

## Gate、Blackboard 与 Artifact

Gate 是主会话执行的叶子节点。主会话先收集证据，再提出聚焦问题，并把决定记录为结构化状态。Worker 不独立向用户提问。

Blackboard 保存跨节点短值；点分名称只是约定，不是 schema。报告、计划、findings、日志和生成内容属于 artifact。

终态操作可以声明 artifact 路径。`artifacts` 只返回这些声明及其 metadata，不扫描 workshop 目录，也不提供独立 artifact index。动态节点可以声明 artifact audience 和 language metadata，供后续受控查询。

## Worker 协议

[单节点 worker 契约](../../../skills/xc-orchestration-runtime/references/subagent-contract.md)采用职责拆分：

1. 主会话取得 ready 节点并启动它。
2. Worker 只使用提供的输入和 reference 执行该节点。
3. Worker 写入持久产物并调用 `complete`、`fail` 或 `block`。
4. 主会话复核 runtime 状态。

Worker 遇到 `state_conflict` 或 `tree_sealed` 时应上报，而不是重试含义不明确的写入。Failed 表示执行失败；blocked 表示缺少可恢复的人类、外部或环境前置条件。两者都不能被静默跳过。

## 转换、完整性与并发

每次写入返回单调递增 revision。调用方可提供 `--expected-revision`，不匹配时返回 `state_conflict`。Runtime 还会串行化本地跨进程写入、验证结构和完整性、使用带 Windows 短暂错误重试的原子替换、重新加载结果并校验 checksum。

受管树包含访问政策和规范化 SHA-256 完整性元数据。读取会报告 mismatch，普通写入要求完整性有效。`repair-integrity --reason` 是显式恢复操作。Checksum 用于检测非受管编辑，不是密码学认证。

## 持久化、检查点与封存

配置优先级为显式 `--config`、从运行树向上找到的最近 `.xcoding/xc-orchestration-runtime.toml`、内置默认值。

当 `auto_commit=true` 时，终态操作把运行树和声明的 artifacts 放入同一个 path-scoped workshop commit。使根节点新近 sealed 的检查点还包含完整独立 SVG。如果渲染、写入或 commit 失败，runtime 会恢复原有运行树和 SVG，并返回 `persisted_uncommitted`；终态转换和 artifact 声明均不被接受。

当 `auto_commit=false` 时，不执行 checkpoint commit 和 checkpoint 路径验证，但状态和声明仍会持久化。非终态修改通常只持久化，不提交，并在下一次 checkpoint 中纳入。

成功的根节点会 sealed，普通修改随后返回 `tree_sealed`。`reopen --reason` 记录新 epoch，并要求所属工作流已获得用户明确批准的原因。这是完成树的恢复机制，不是常规继续执行。

公开命令契约见 [runtime protocol](../../../skills/xc-orchestration-runtime/references/runtime-protocol.md)。
