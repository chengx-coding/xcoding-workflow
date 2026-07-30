[English](../../orchestration/overview.md)

# 编排概览

XC 编排把复杂、长期运行的 Agent 工作流表示为具有确定性调度和持久状态的受管树。Markdown 继续负责目标、政策、领域方法、节点说明和验收标准；编排服务负责可执行结构、状态转换、持久化、完整性和查看。

这种分离首先服务于上下文和控制。主会话只需请求下一批就绪工作，不必加载整个流程；worker 只接收一个自包含节点，不必解释完整过程；顺序调度、条件求值、循环推进和父状态聚合等确定性操作由代码完成，而不是让模型反复判断。

## 服务边界

架构包含三个公开服务：

- [`xc-orchestration-runtime`](../../../skills/xc-orchestration-runtime/SKILL.md) 是领域中立的控制面，负责运行时状态、调度、转换、完整性、受控持久化、快照和本地 Viewer。
- [`xc-orchestration-author`](../../../skills/xc-orchestration-author/SKILL.md) 把获批的工作流设计转换为经过验证的 schema version 1 模板。它负责 flow spec、模板构建和 authoring 验证，但不执行工作。
- [`xc-orchestration-viewer`](../../../skills/xc-orchestration-viewer/SKILL.md) 是供人类查看的无脚本发现 facade。server、快照解释和前端实现均由 runtime 所有。

领域 Skill 负责工作的含义，包括模板、任务说明、gate、artifact 契约、blackboard 键、验收标准和领域 reference。领域 Skill 通过公开操作调用 runtime，不复制其调度器、状态机、解析器或 Viewer。

主会话是 orchestrator：初始化或恢复运行树、请求 ready 节点、启动委派、处理 `executor=main` gate，并复核结果。它可以执行明确分配给 `executor=main` 的工作，并非只能委派。subagent 是单节点 worker，不查看同级节点、未来节点或全局控制流。

## 设计影响

该模型有选择地组合了多种成熟方法：

- 行为树提供 sequence、parallel、层级状态和 blackboard 思路。
- 工作流系统提供显式依赖、持久任务状态和 artifact 思路。
- 层级任务分解提供从目标到任务的结构。
- 状态机提供受保护的生命周期转换。
- worker queue 提供调度者与 worker 的边界。

这些只是设计影响，不表示 XC 完整实现了其中任何一种形式化模型。系统以树为主，只提供有限的显式依赖边，不是通用 DAG 引擎。

## 持久化与公开边界

受管模板和运行树当前以 XML 作为持久表示，但 XML 不是供 Agent 编辑的接口。Agent 使用 author 和 runtime 公开命令；操作协议和确定性语义才是公开抽象。

Runtime 刻意保持领域中立，只理解四种控制节点：`composite`、`task`、`gate` 和 `loop`。调研、评审、撰写、测试和修复等业务概念属于 `role`、`metadata.*` 和节点契约。

共享信息按体量和用途拆分：

- blackboard 保存影响后续调度或决策的短值。
- artifact 保存报告、计划、代码变更、验证证据和其他丰富输出。
- runtime 在节点终态操作中记录声明的 artifact 路径，但不提供独立 artifact store。

Viewer 只读，仅消费 runtime 快照，不提供生命周期或 blackboard 修改端点。运行状态变更仍通过 runtime CLI 完成。

## 可复用工作流模式

控制原语可以组合成常见模式，但这些模式不是 runtime 语法。

### 调研、综合、Gate、执行

并行执行相互独立的调研，综合证据，通过一个集中的主会话 gate 提问，再执行获批工作。这样用户决定有证据支撑，也避免 worker 零散提问。

### 动态矩阵

发现目标集合，为每个目标向开放 dynamic group 添加一个自包含节点或嵌入子树，显式关闭该组，执行子节点并汇总结果。并行子节点必须拥有互不冲突的写入范围。

### 评审与返工

把基于 role 的评审和条件返工任务放入有界 loop。评审 findings 和关闭权限仍由领域契约定义；runtime 只提供循环、条件、状态和 blackboard 机制。

### Gate 控制的风险操作

分析风险、准备明确选项、在 gate 中获取用户决定、执行选定方案并验证结果。Gate 是集中的控制点，不能替代自包含 worker 说明。

## 后续阅读

- [运行时模型](runtime-model.md)介绍对象、ID、调度、状态、循环、恢复和持久化。
- [模板创作](authoring.md)介绍 flow spec、模板设计、验证和 smoke test。
- [Viewer](viewer.md)介绍只读本地 server、UI、安全边界和生命周期。
- [设计决策与未来可能性](design-decisions-and-future.md)记录当前取舍、非目标和明确未承诺的设想。
