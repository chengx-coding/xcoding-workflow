**语言：** [English](../../concepts/architecture.md) | **简体中文**

# 架构

## 使命

XC 是一套可移植、由 Skill 驱动的编码工作流。它覆盖发现、设计、实现、诊断、验证、评审、修复和交付，同时把项目专属策略留在通用工作流核心之外。

本仓库是工作流能力的规范源，不是消费项目的源码树或 workshop 历史。

## 规范源

仓库有两类规范工作流创作源：

- `skills/xc-*/` 负责通用工作流 Skill。每个包的 `SKILL.md` 是公开的发现和操作契约，`references/`、`scripts/` 与 `assets/` 为该契约提供支持。
- `agents-src/agents/` 负责持久、可移植的 subagent 定义。已跟踪的 [`xc-delegated-agent` 定义](../../../agents-src/agents/xc-delegated-agent.md)是工具中立的规范 agent 示例。

`agents-src/agents/` 下的规范 agent 定义遵循同一条命名规则。该规则约束这个目录里的每一个规范 agent 定义，而不是只约束当前这一个。

- **`xc-` 前缀。** 规范 agent 标识符以 `xc-` 开头，该前缀同时落在文件词干（规范文件名去掉 `.md` 后的部分）与 frontmatter `name` 上。标识符因此与 `skills/xc-*/` 共用同一个可移植的 `xc-` 命名空间。与 Skill 一侧不同，agent 一侧的该前缀没有任何机械检查强制。
- **`-agent` 后缀。** 标识符形态为 `xc-<描述性名称>-agent`。用户键入的 handle（宿主对外暴露的身份串）是 Claude Code、Codex 与 Trae 生成物中的 `name` 字段，或 OpenCode 的文件名，而不是路径，因此安装目录里的 `agents` 一词在路径意义上冗余、在 handle 意义上不冗余。该后缀正是 agent 标识符与 Skill 标识符的区分手段，因为 `skills/` 下没有任何包名以 `-agent` 结尾。
- **词干与名称相等。** 规范文件的词干逐字等于 frontmatter `name`。Claude Code、Codex 与 Trae 逐字输出该名称，因此在这三者上 `stem == canonical name == emitted name` 按构造成立。这条相等没有机械检查强制：导出器只要求 `name` 与 `description` 非空，其 check 模式与构建期的精确集合策略都只比较路径集合，从不比较词干与名称。只改其中一侧会留下一个被现有全部守卫接受的分歧状态。
- **不输出 name 字段的宿主。** OpenCode 输出不携带 `name` 字段，其身份就是文件名，不变式在该宿主上退化为 `stem == 生成文件名`；该文件名由按词干推导的导出过程保证，无须读取任何字段。这条陈述的对象是本仓库发出的产物；OpenCode 本身是否以该文件名作为用户可见的 handle，属于本仓库任何受跟踪文件都未陈述的外部程序行为。
- **H1 标题。** 规范 agent 定义把标识符逐字写成 H1，采用反引号包裹的小写原形，例如 `` # `xc-delegated-agent` ``。H1 会逐字进入全部 4 个生成正文，因此它与标识符同属一条身份链上的可见面。
- **字符类。** 标识符匹配 `[a-z0-9]+(?:-[a-z0-9]+)*`：ASCII 小写字母与数字，段之间为单个连字符。该字符类约束文件词干与 frontmatter `name`，而词干与名称相等已使两者成为同一个值；H1 中的反引号不属于被约束的值。今天没有任何检查强制该字符类。
- **适用范围。** 规则适用于 `agents-src/agents/` 下的每一个规范 agent 定义。构建期从规范词干集合推导期望的生成文件集合，因此关于词干的规则天然是集合级规则；当前清单只有一个元素，这是当下的事实，而不是设计决定。
- **只成文的强度。** 本规则只成文：它不新增任何机械检查，全部约束力等于文档纪律。退役名不被阻止，因为 Skill 一侧有退役包阻止表，而 agent 一侧没有对应机制，因此一个退役的 agent 名称可以重新出现而不触发任何失败。尤其是，由于没有任何工具比较文件词干与 frontmatter `name`，将来任何一次只改一侧的改动仍会通过 `python agents-src/export_agents.py --check`。

任何派生产物都必须在规范源修改之后更新。Skill 之间只通过 Skill 名称和已记录的公开参数通信，一个 Skill 不会读取另一个 Skill 的私有 reference 或脚本。

有一个 Skill 拥有面向用户的渲染面，而不是受管 Markdown 文档。[`xc-change-report`](../../../skills/xc-change-report/SKILL.md) 拥有变更报告：单个离线 HTML 文件、用于证明该报告的覆盖清单，以及确定性校验器。其撰写标准留在 [`xc-document`](../../../skills/xc-document/SKILL.md) 的共享人类可读契约中，正文语言则遵循 work order 固定的文档语言，因此所有面向人类的产出由同一套标准约束，而不是每个渲染器各存一份。

## 生成输出与适配器

`agents-src/claude-agents/`、`agents-src/opencode-agents/`、`agents-src/codex-agents/` 和 `agents-src/trae-agents/` 是面向特定目标生成的 agent 定义。[agent 导出器](../../../agents-src/export_agents.py)会验证规范定义并复现这些输出。

Agent 宿主的发现位置和安装目录属于适配器，不是新的事实源。例如，已跟踪的 [Skill 同步脚本](../../../build_agents.py)会把规范 Skill 包镜像到当前检出的本地发现目录，但变更仍然必须从 `skills/xc-*/` 开始。

这种分离把工具专属的元数据、权限和文件格式限制在边缘，同时保持共享行为可移植。

## Skill 内部 Worker 与通用 delegated Agent

[`xc-delegation`](../../../skills/xc-delegation/SKILL.md) 允许所属 Skill 把私有 worker profile 保存在 `assets/workers/<profile-id>/` 下，同时复用向每个受支持宿主交付的持久 `xc-delegated-agent`。私有 profile 不是第二份持久 Agent 定义：它只能从所属 Skill 根目录解析，必须通过严格 schema 校验，并针对某个正在运行的节点 attempt 编译成一份确定性的 dispatch envelope。

Skill 内部的源 profile 采用 current-only 格式：根对象不携带 `schema_version`，已经废弃的根版本字段会被拒绝，而不会静默迁移。主会话先从 runtime 获取只读 assignment packet，再由 `xcoding delegate prepare` 对六个彼此独立的能力层取交集：profile 请求、XC 上限、项目上限、节点拥有的授权、调用方收窄和宿主声明。任何一层都不能放宽此前的拒绝。Dynamic overlay 只能进一步收窄已解析 profile；无效或不受支持的 v1 输入会失败关闭，不会回退到 prompt 定义的角色。

`xc-delegated-agent` 提供两种显式兼容模式。`prepared-profile` 只接受标记为 dispatch-authoritative 的已准备 envelope，并通过分配到的进程内 terminal binding 报告恰好一种获准节点结果。`legacy-prompt` 只接受显式选择的 prompt 定义角色，且绝不声称获得 v1 校验或强制。若一个私有角色变为跨 Skill 共享、可由用户直接选择，或依赖独立的持久模型或权限身份，就应提升为 `agents-src/agents/` 下的规范定义。

宿主 capability statement 是构建与 setup 资源，不是第三方宿主强制执行 envelope 的证明。当前四份声明均为 `validated-only`，adapter version 尚未验证；network 与 secret 能力仍不受支持。只有匹配固定版本的端到端证据才能使用 `enforced`。

## Package、Bundle 与 Runtime Application 基础设施

仓库还在 `pyproject.toml`、`src/xcoding/`、`build_support/`、`scripts/` 和 `.github/` 中包含产品 package 与 release 验证基础设施。它构建 `xcoding-workflow` package 和不可变 Bundle，并验证与具体 candidate 无关的 package 契约。这只是仓库构建边界，不是新的工作流创作源。

Bundle 是构建时快照。`skills/xc-*/` 仍是 Skills 的唯一规范源；package runtime
和 Viewer 实现及资源位于 `src/xcoding/`。`agents-src/agents/` 仍是持久 agent
定义的唯一规范源。面向特定宿主生成的 agent 定义只是经过校验后供 Bundle
adapter 使用的构建输入，不是事实源。`build_support/host_adapters.json` 只声明
如何把这些生成输入映射到 Bundle。当前 Bundle 不再包含 Viewer 实现 partition。

`src/xcoding/runtime/` 是运行时树模型、Runtime Application Service、持久化
事务、共享 26 命令规范、typed read-only query facade 和默认模板的可编辑源。
`src/xcoding/viewer/` 拥有 Viewer server、picker、lifecycle 和静态前端。
`src/xcoding/daemon/` 拥有带认证的只读工具 API。

匹配的 `xcoding` package 是必要依赖。`xcoding runtime` 直接调用 Runtime
Application Service；`xcoding viewer` 和 `xcoding daemon` 暴露其他 package
surface。Runtime Skill 只保留薄 legacy `orchestration.py` adapter，通过已安装
console command 执行 `xcoding runtime`。工具缺失时返回
`xcoding_unavailable`，没有本地 fallback。

`xcoding daemon serve` 是可选本地只读 transport。它只绑定 `127.0.0.1`，
要求 process-lifetime bearer token 和精确 Host/Origin 检查，只接受启动时传入
的 runtime 文件，暴露十个 typed read-only query，并传输有界、非持久的 SSE
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
