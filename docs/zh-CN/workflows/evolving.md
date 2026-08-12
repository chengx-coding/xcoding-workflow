**语言：** [English](../../workflows/evolving.md) | **简体中文**

# 演进 XC

工作流维护采用与产品工作相同的证据、批准、实现、验证和评审纪律。[`xc-workflow-evolution`](../../../skills/xc-workflow-evolution/SKILL.md)入口首先区分可移植核心变更与项目专属桥接变更。

## 选择演进范围

| Scope | 适用对象 |
| --- | --- |
| `portable-core` | 通用 Skill 契约、reference、脚本、asset 和共享工作流行为 |
| `project-bridge` | 单个项目的受管工作流指引和项目专属约定 |
| `agent-export` | 规范可移植 agent、目标元数据、导出器行为和生成定义 |
| `orchestration-template` | 受管 flow specification、生成模板、调度结构和 gate |
| `health-check` | 验证工作流 asset 及其派生输出的专项维护 |

大范围架构变更必须在实现前具备证据、可行备选方案、独立评审和显式用户 gate。

窄范围工作流维护可以在成比例规划后显式使用 `xc-work operation=adaptive-run`。广泛的 portable-core、orchestration-template 和 agent-export 变更即使用户要求 fast pace，仍保留 required analysis、solution、gate、verification 和 review capability。现有 workflow-evolution 路由默认继续使用完整 `run` 生命周期。

## 先修改规范源

### Skill

在 `skills/xc-*/` 下修改通用包。Frontmatter、正文、reference、模板和面向 agent 的指引应使用英文，并且不包含消费项目事实。除非获批变更明确修订公开接口，否则应保持公开参数和跨 Skill 边界。

修改 Skill 后，运行已跟踪的 [Skill 同步脚本](../../../build_agents.py)，让当前检出的本地 Agent 发现适配器与规范包一致。不能只修复适配器副本。

### Agent

在 `agents-src/agents/` 下修改持久、可移植的定义。工具、模型、权限、sandbox 和 frontmatter 差异应通过目标元数据表达，而不是分叉共享正文。

运行已跟踪的 [agent 导出器](../../../agents-src/export_agents.py)，重新生成 Claude Code、OpenCode、Codex 和 Trae 定义。生成的目标文件是可评审输出，不是编辑入口。

### 编排

使用 [`xc-orchestration-author`](../../../skills/xc-orchestration-author/SKILL.md)修改已批准的 JSON flow specification、执行验证并重新构建受管模板。领域 Skill 负责节点指引、验收条件和 artifact；运行时保持领域中立。

不要手工编辑生成模板或受管运行时树。运行时状态只能通过 [`xc-orchestration-runtime`](../../../skills/xc-orchestration-runtime/SKILL.md)公开接口修改。

### 项目桥接

项目桥接变更通过文档演进、验证、评审和必要 gate 更新受管概念路径 `.xcoding/WORKFLOW.md`。它不会把项目命令、仓库事实或业务规则复制到可移植 Skill 中。

## 验证每个派生面

| 变更面 | 必需证据 |
| --- | --- |
| Skill 包 | 名称和 frontmatter 验证、公开契约与资源路径检查、Agent 发现同步、专项测试及适用的更广测试 |
| 规范 agent 或导出器 | 导出所有受支持目标，运行 `python agents-src/export_agents.py --check`，并检查每一项生成 diff |
| 编排 flow 或模板 | 验证 flow specification 与模板，再通过 `init` 和 `next` 对公开运行时路径做 smoke test；针对受影响的调度、gate、循环、恢复、完整性或并发扩大测试 |
| 项目桥接 | 受管文档验证、需要时的独立评审，以及该桥接声明的检查 |
| 公开文档 | 结构与链接检查，以及独立的中英文语义评审 |

先运行专项检查，再根据被修改契约和影响范围扩大验证。生成文件检查失败时，应在规范源修复。

## 文档影响与多语言维护

每次 XC 迭代都要判断其行为、命令、路径、边界或示例是否影响公开文档。在同一变更中更新所有受影响的英文页面及其精确 `docs/zh-CN/` 镜像，同时维护双向语言切换和所有提及该页面的导航。

英文页面是规范版本；中文页面必须保持相同主题、事实边界和实质信息，但不要求逐行翻译。自动检查负责结构、链接、Git 可见性和目录不变量，独立双语评审仍需验证语义一致性。

公开页面只能链接干净检出中存在的文件，不链接 workshop 状态、本地 Agent 发现 asset、项目指引或其他被忽略、排除的维护文件。

Release 契约定义了显式 Python、平台与 Agent 宿主矩阵。文档只能描述该契约声明的正式基线和实验性 cell；只有 candidate-bound 证据验证全部必需 cell 后，公开 release 才能声明支持。可接受的 Python 版本、检测到的 executable 或未经验证的宿主都不得被提升为兼容性保证。
