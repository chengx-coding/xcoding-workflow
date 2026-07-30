**语言：** [English (英文)](../../orchestration/design-decisions-and-future.md) | **简体中文 (Simplified Chinese)**

# 设计决策与未来可能性

本页严格区分当前设计理由与设想。当前行为由已跟踪的 [`runtime`](../../../skills/xc-orchestration-runtime/SKILL.md)、[`author`](../../../skills/xc-orchestration-author/SKILL.md) 和 [`viewer`](../../../skills/xc-orchestration-viewer/SKILL.md) 契约定义。

## 当前设计决策

### 以树为主的控制

XC 使用层级化 sequence、parallel、switch、dynamic group 和 loop。有限依赖用于必要的跨分支前置条件，不把 runtime 变成通用 DAG 引擎。

取舍：树结构更容易解释、稳定化、可视化和局部委派，但不适合表达高度互联的依赖图。

### 确定性 Runtime，领域所有的含义

Runtime 负责调度、转换 guard、聚合、完整性和持久化；领域 Skill 负责 instructions、acceptance、评审权限、失败政策和 artifact 含义。

取舍：新增领域工作流不需要修改 runtime，但领域包必须编写完整节点契约，不能依赖 runtime 理解业务。

### 四种控制节点

`composite`、`task`、`gate` 和 `loop` 覆盖 runtime 控制语义。评审、调研、撰写和修复等 role 仍是领域标签。

取舍：模板保持可移植，runtime 避免不断扩张的业务类型枚举；读者则需要查看 role 和节点 instructions 才能理解领域含义。

### 小型条件集合

条件只支持 truthy、negation、equality 和 inequality。复杂判断属于可执行 task，由其写入简单 blackboard 结果。

取舍：模板保持可测试、无副作用，但复杂决定可能需要额外 task。

### 有界的轮末循环

Loop 只在一轮结束后决定是否继续，并且每个 loop 都有最大轮次和上限结果。

取舍：评审返工可以确定性收敛和恢复，但不提供命令式的轮次中途控制。

### 集中的主会话 Gate

用户交互由 `gate executor=main` 表示，并放在相关证据收集之后。

取舍：用户决定集中且全局可见，但模板必须有意识地把 gate 放在重要操作之前。

### 紧凑 Blackboard，持久 Artifact

Blackboard 保存短控制值，报告和其他丰富输出保存在 workshop artifact 或外部目标系统中。

取舍：runtime 状态保持紧凑且适合调度，但消费者需要沿已声明 artifact 路径查看完整证据。

### 单节点 Worker

主会话启动工作；每个 worker 执行一个节点并报告终态；主会话复核状态。

取舍：委派边界和并行所有权清晰，但 runtime 不提供 worker pool 或自动 capability matching。

### 受管本地持久化

运行树是通过公开操作访问的受管 schema version 1 XML。写入使用验证、锁、revision、原子替换和 checksum 复核。

取舍：本地运行可检查、可恢复，但不支持任意持久化后端。

### 事务性 Checkpoint 与 Sealing

启用自动 workshop commit 时，终态 checkpoint 同时接受运行树转换和声明的 artifacts。Commit 或 render 失败会恢复之前的受管状态。成功根节点会 sealed，只有显式提供原因的 reopen 操作才能重新打开。

取舍：已接受状态和 checkpoint 证据不会静默分离，但 Git 或渲染失败会阻止终态被接受，而不是仅给出 warning。

### 只读 Viewer

Viewer 只消费快照，不能修改编排状态。它绑定 loopback，默认端口 `20668`，使用自定义静态浏览器代码而非 D3。

取舍：查看功能具有较小的安全和正确性边界，但操作人员必须使用 runtime 命令执行变更。

## 当前非目标

当前系统不提供：

- 通用 DAG 引擎或可插拔政策调度器。
- 通用 retry、timeout、token/time/cost budget 或 retry metrics。
- Worker pool、capability matching 或强制 worker cancellation。
- 用于中断 loop、跳过同级节点、终止子树或中止运行的 runtime 控制信号。
- 独立 typed artifact index 或 artifact storage service。
- Event sourcing 或 runtime event log。
- 任意持久化格式、持久化中立 core 或远程编排服务。
- 可写 Viewer 或暴露到网络的 dashboard。

名为 `tool` 和 `service` 的 executor 不表示存在 capability registry 或自动远程执行。`artifacts` 命令报告终态声明，不是已索引的 provenance database。

## 非规范、未承诺的可能性

本节全部内容均为非规范信息，不是路线图、承诺、排期、兼容保证或获批设计。只有经过单独批准的工作流变更，并补齐契约、测试和迁移分析后，某项可能性才会成为 XC 的组成部分。

可以调查的方向包括：

- 更好的 author 诊断，用于解释无效引用、不可达分支或意外的首批 ready 结果。
- 基于现有 runtime 状态的额外只读快照摘要和比较工具。
- 本地 Viewer 的无障碍和大型树导航改进。
- 更多有界评审、动态矩阵和 gate 风险控制的可复用组合示例。
- 当重复出现的真实工作流证明存在通用需求时，对已验证条件或模板工具进行窄范围增强。

本页没有选择或承诺任何实现语言、服务架构、替代持久化后端、调度器插件系统、budget 模型、worker-pool 设计、artifact-index 模型、cancellation 协议或 event-sourcing 模型。此类主题必须通过独立证据和批准决定，不能从本页推断。

## 决策如何演进

编排语义变更必须保持领域中立和公开边界，并满足：

1. 证明存在领域模板无法清晰处理的重复需求。
2. 明确定义状态、失败、恢复和兼容契约。
3. 补齐 author 验证和 runtime 转换测试。
4. 只有只读 snapshot 契约变化时才更新 Viewer。
5. 文档清楚区分已发布行为和仍未承诺的可能性。
