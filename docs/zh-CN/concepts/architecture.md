**语言：** [English](../../concepts/architecture.md) | **简体中文**

# 架构

## 使命

XC 是一套可移植、由 Skill 驱动的编码工作流。它覆盖发现、设计、实现、诊断、验证、评审、修复和交付，同时把项目专属策略留在通用工作流核心之外。

本仓库是工作流能力的规范源，不是消费项目的源码树或 workshop 历史。

## 规范源

仓库有两类规范工作流创作源：

- `skills/xc-*/` 负责通用工作流 Skill。每个包的 `SKILL.md` 是公开的发现和操作契约，`references/`、`scripts/` 与 `assets/` 为该契约提供支持。
- `agents-src/agents/` 负责持久、可移植的 subagent 定义。已跟踪的 [delegate agent 定义](../../../agents-src/agents/delegate-agent.md)是工具中立的规范 agent 示例。

任何派生产物都必须在规范源修改之后更新。Skill 之间只通过 Skill 名称和已记录的公开参数通信，一个 Skill 不会读取另一个 Skill 的私有 reference 或脚本。

## 生成输出与适配器

`agents-src/claude-agents/`、`agents-src/opencode-agents/`、`agents-src/codex-agents/` 和 `agents-src/trae-agents/` 是面向特定目标生成的 agent 定义。[agent 导出器](../../../agents-src/export_agents.py)会验证规范定义并复现这些输出。

Agent 宿主的发现位置和安装目录属于适配器，不是新的事实源。例如，已跟踪的 [Skill 同步脚本](../../../build_agents.py)会把规范 Skill 包镜像到当前检出的本地发现目录，但变更仍然必须从 `skills/xc-*/` 开始。

这种分离把工具专属的元数据、权限和文件格式限制在边缘，同时保持共享行为可移植。

## Package、Bundle 与 Runtime Application 基础设施

仓库还在 `pyproject.toml`、`src/xcoding/`、`build_support/`、`scripts/` 和 `.github/` 中包含产品 package 与 release 验证基础设施。它构建 `xcoding-workflow` package 和不可变 Bundle，并验证与具体 candidate 无关的 package 契约。这只是仓库构建边界，不是新的工作流创作源。

Bundle 是构建时快照。`skills/xc-*/` 仍是 Skills 的唯一规范源；package runtime
和 Viewer 实现及资源位于 `src/xcoding/`。`agents-src/agents/` 仍是持久 agent
定义的唯一规范源。面向特定宿主生成的 agent 定义只是经过校验后供 Bundle
adapter 使用的构建输入，不是事实源。`build_support/host_adapters.json` 只声明
如何把这些生成输入映射到 Bundle。当前 Bundle 不再包含 Viewer 实现 partition。

`src/xcoding/runtime/` 是运行时树模型、Runtime Application Service、持久化
事务、共享 23 命令规范、typed read-only query facade 和默认模板的可编辑源。
`src/xcoding/viewer/` 拥有 Viewer server、picker、lifecycle 和静态前端。
`src/xcoding/daemon/` 拥有带认证的只读工具 API。

匹配的 `xcoding` package 是必要依赖。`xcoding runtime` 直接调用 Runtime
Application Service；`xcoding viewer` 和 `xcoding daemon` 暴露其他 package
surface。Runtime Skill 只保留薄 legacy `orchestration.py` adapter，通过已安装
console command 执行 `xcoding runtime`。工具缺失时返回
`xcoding_unavailable`，没有本地 fallback。

`xcoding daemon serve` 是可选本地只读 transport。它只绑定 `127.0.0.1`，
要求 process-lifetime bearer token 和精确 Host/Origin 检查，只接受启动时传入
的 runtime 文件，暴露九个 typed read-only query，并传输有界、非持久的 SSE
摘要。`xcoding runtime` 继续在本地直接执行，不发现或启动 daemon；
`xcoding viewer` 仍是独立的浏览器查看 surface。

这些基础设施尚未发布，也没有公开 package 来源。因此当前除安装 Skills 外，
还需要维护者提供、经过验证的本地 wheel。阶段 1 所需的外部 matrix 证据仍
不可用，因此结论保持 `unknown` 和 `no-go`；不承诺 package、平台、Python
或 Agent 宿主兼容性。Daemon 不提供 remote bind、runtime mutation service、
durable operation journal、replay、service install、discovery 或默认
transport 切换；后续 mutation、remote transport 或发布工作需要单独批准。

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
