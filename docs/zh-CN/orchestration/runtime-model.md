**语言：** [English](../../orchestration/runtime-model.md) | **简体中文**

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

## 限定范围的 Control Packet

`task` 或 `gate` 叶子节点可以声明一个或多个领域命名的 `metadata.control_packet.category.*` 类别。每个类别提供紧凑 JSON selector 数组、`min_sources` 和 `artifact_min`。`node:<runtime-id>` 选择一个来源；`bb:<key>` 读取一个 blackboard 标量，该值必须是由唯一 runtime ID 组成的非空紧凑 JSON 数组。类别由领域拥有；runtime 只验证名称、展开结果、终态、可投影结果内容和阈值。

`metadata.control_packet.blackboard_keys` 是另一个紧凑 JSON 数组，用于选择允许投影的标量。用于查找 source ID 的 blackboard key 不会自动暴露，除非它也被显式选择。声明只属于 target 叶子节点：ancestor 不能声明、贡献或覆盖 packet metadata。

`control-packet --node` 返回 target 契约、已声明来源投影、选定 blackboard 值、局部 blocker 和控制动作。它绝不会返回 target children、来源 instructions、未声明的 sibling 或 future-node 数据、未选 blackboard 值、完整 blackboard、未声明 artifact 或完整树。来源只能贡献投影后的结果字段：身份、标题、role、状态、summary、已声明 artifact、结构化 gate outcome 与 decision、failure 或 block 原因，以及已保存的归一化 check。

缺少声明时返回 `control_packet_not_declared`。Selector、来源、阈值或选定键非法或不满足时返回 `control_packet_unavailable`，不返回残缺 packet，也不改变 revision。Source ID 只提供证据，不授予启动或修改该节点的权限。

## Gate、Completion、Blackboard 与 Artifact

Gate 是主会话执行的叶子节点。主会话先收集证据，再提出聚焦问题，并把决定记录为结构化状态。Worker 不独立向用户提问。

Opt-in gate 声明唯一的 lowercase-kebab outcome 列表、显式 `decision_required` 布尔值，以及可选的 outcome blackboard key。`complete --gate-outcome` 记录允许的 outcome，`--decision` 提供必需说明。结果存储和可选 outcome key 更新是原子操作，同时用 `--set` 写同一 key 会被拒绝。Runtime 会验证声明与值，但不认证实际 CLI 调用者。

Runtime 有意不判断哪些领域 outcome 属于接受结果；领域 flow spec 使用普通 reactive condition、switch 和 dynamic group 机械表达该决策。当前生命周期模板只为显式接受值选择有实质后果的继续路径；每个已声明的非接受值都会选择开放 recovery 分支，未知 switch 值则进入 blocked。后继 recovery gate 可以原子地把 outcome 替换为接受值，并重新激活正常分支。被跳过的可选 gate 使用规范 flow 中由领域声明的安全默认值。

Opt-in completion metadata 可以要求 `summary` 与 `validation`、artifact 数量和由 literal 或 blackboard 选择的 artifact 路径，以及归一化 check receipt。Runtime 在成功前验证 receipt 的形状、大小、唯一性、已声明名称、布尔成功值、subject 和标量 facts；拒绝时树和 revision 不变。`fail` 与 `block` 不应用成功完成要求。

归一化 receipt 是不可信的调用方自报告，不是执行证明。它没有签名，也没有 claimant binding 或 attestation。Runtime 不导入或运行领域 validator，因此结构和值完全匹配预期的伪造 receipt 会被接受。调用方仍必须实际执行 validator，检查其进程和顶层结果，并且只传入归一化 receipt。

Blackboard 保存跨节点短值；点分名称只是约定，不是 schema。报告、计划、findings、日志和生成内容属于 artifact。

终态操作可以声明 artifact 路径。`artifacts` 只返回这些声明及其 metadata，不扫描 workshop 目录，也不提供独立 artifact index。动态节点可以声明 artifact audience 和 language metadata，供后续受控查询。

## Worker 协议

[单节点 worker 契约](../../../skills/xc-orchestration-runtime/references/subagent-contract.md)采用职责拆分：

1. 主会话取得 ready 节点，并为 opt-in 叶子请求其 control packet。
2. 主会话启动 packet target，只委派该节点。
3. Worker 只使用提供的 packet、输入和 reference 执行该节点。
4. Worker 写入持久产物并调用 `complete`、`fail` 或 `block`。
5. 主会话复核 runtime 状态。

Worker 遇到 `state_conflict` 或 `tree_sealed` 时应上报，而不是重试含义不明确的写入。Failed 表示执行失败；blocked 表示缺少可恢复的人类、外部或环境前置条件。两者都不能被静默跳过。

## 转换、完整性与并发

每次写入返回单调递增 revision。调用方可提供 `--expected-revision`，不匹配时返回 `state_conflict`。Runtime 还会串行化本地跨进程写入、验证结构和完整性、使用带 Windows 短暂错误重试的原子替换、重新加载结果并校验 checksum。

受管树包含访问政策和规范化 SHA-256 完整性元数据。读取会报告 mismatch，普通写入要求完整性有效。`repair-integrity --reason` 是显式恢复操作。Checksum 用于检测非受管编辑，不是密码学认证。

## 持久化、检查点与封存

配置优先级为显式 `--config`、从运行树向上找到的最近 `.xcoding/xc-orchestration-runtime.toml`、内置默认值。

当 `auto_commit=true` 时，终态操作把运行树和声明的 artifacts 放入同一个 path-scoped workshop commit。使根节点新近 sealed 的检查点还包含完整独立 SVG。如果渲染、写入或 commit 失败，runtime 会恢复原有运行树和 SVG，并返回 `persisted_uncommitted`；终态转换和 artifact 声明均不被接受。

当 `auto_commit=false` 时，不执行 checkpoint commit 和 checkpoint 路径验证，但状态和声明仍会持久化。非终态修改通常只持久化，不提交，并在下一次 checkpoint 中纳入。

成功的根节点会 sealed，普通修改随后返回 `tree_sealed`。`reopen --reason` 记录新 epoch，并要求所属工作流已获得用户明确批准的原因。这是完成树的恢复机制，不是常规继续执行。

## 兼容性与限制

Control packet、completion requirement、归一化 receipt 和 structured gate 都是 `schema_version="1"` 内的 opt-in 扩展。不带对应 metadata 的现有 schema-version-1 节点和 gate 保留 legacy 命令与结果形状。更早 schema 格式仍不受支持；系统不会通过 ancestor 推断叶子声明来改造在途树。

Scoped packet 减少运行时协议披露，但 runtime 无法阻止节点启动前的普通宿主工具调用，启动后也不代理宿主工具。本版本没有可信 validator 执行、claim binding、typed blackboard、host mediation 或模型专用执行 profile。模型能力不能扩大 packet 范围或削弱受管控制。

任何名为 `context_bytes` 的测量都只统计归一化 UTF-8 协议 payload 字节。它不是 token 数，也不对模型时延、执行时延、成本或输出质量作出任何声明。

公开命令契约见 [runtime protocol](../../../skills/xc-orchestration-runtime/references/runtime-protocol.md)。
