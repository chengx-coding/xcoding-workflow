[English](../../concepts/architecture.md)

# 架构

## 使命

XC 是一套可移植、由 Skill 驱动的编码工作流。它覆盖发现、设计、实现、诊断、验证、评审、修复和交付，同时把项目专属策略留在通用工作流核心之外。

本仓库是工作流能力的规范源，不是消费项目的源码树或 workshop 历史。

## 规范源

仓库有两类规范创作源：

- `skills/xc-*/` 负责通用工作流 Skill。每个包的 `SKILL.md` 是公开的发现和操作契约，`references/`、`scripts/` 与 `assets/` 为该契约提供支持。
- `agents-src/agents/` 负责持久、可移植的 subagent 定义。已跟踪的 [delegate agent 定义](../../../agents-src/agents/delegate-agent.md)是工具中立的规范 agent 示例。

任何派生产物都必须在规范源修改之后更新。Skill 之间只通过 Skill 名称和已记录的公开参数通信，一个 Skill 不会读取另一个 Skill 的私有 reference 或脚本。

## 生成输出与适配器

`agents-src/claude-agents/`、`agents-src/opencode-agents/` 和 `agents-src/codex-agents/` 是面向特定目标生成的 agent 定义。[agent 导出器](../../../agents-src/export_agents.py)会验证规范定义并复现这些输出。

Agent 宿主的发现位置和安装目录属于适配器，不是新的事实源。例如，已跟踪的 [Skill 同步脚本](../../../build_agents.py)会把规范 Skill 包镜像到当前检出的本地发现目录，但变更仍然必须从 `skills/xc-*/` 开始。

这种分离把工具专属的元数据、权限和文件格式限制在边缘，同时保持共享行为可移植。

## 通用核心与项目桥接

通用 Skill 定义可复用的生命周期行为，不会硬编码消费项目的语言、框架、仓库布局、构建命令、测试工具、文档策略、业务规则或项目专属能力。

每个消费项目通过概念路径 `.xcoding/WORKFLOW.md` 提供这些选择，可选的项目知识指引位于 `.xcoding/KNOWLEDGE.md`。这些 workshop 本地路径有意不作为公开文档链接。

实际生效的数据流为：

```text
用户请求
  -> 通用 xc-* 生命周期契约
  -> 项目桥接与已声明的项目知识
  -> 项目代码、测试和受管 workshop
```

通用核心决定何时需要项目知识，桥接负责提供事实，但不能覆盖运行时安全规则、Skill 公开契约或编排访问控制。

## 主会话、Worker 与公开边界

主会话是编排者。它打开或恢复 work order，向运行时请求就绪工作，启动可执行节点，处理用户 gate，每次只委派一个节点，并在 worker 返回后核对运行时状态。

Worker 接收一个运行中的节点及其有界输入。它只执行该节点，写入已声明的 artifact，并通过运行时公开接口报告完成、失败或阻塞。它不会检查兄弟或未来节点、改变全局控制流，也不会直接读取受管运行时文件。

[编排运行时契约](../../../skills/xc-orchestration-runtime/SKILL.md)是读取受管树、执行状态转换与调度、处理完整性以及生成快照的唯一边界。长篇分析和报告属于 artifact；运行时 blackboard 只保存影响控制流的短值。

这些边界让生命周期状态可恢复、可审计，同时避免领域 Skill 或 worker 与运行时存储格式耦合。
