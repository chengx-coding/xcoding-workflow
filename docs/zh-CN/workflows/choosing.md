**语言：** [English](../../workflows/choosing.md) | **简体中文**

# 选择工作流

应根据项目当前状态和目标结果选择生命周期。不要仅因为工作量较大就选择 feature 生命周期，也不要用普通 work order 隐式创建 feature。

## 决策表

| 场景 | 入口 | 结果 |
| --- | --- | --- |
| 项目首次采用 XC，或缺少必需的 workshop 桥接文档 | [`xc-workshop-setup`](../../../skills/xc-workshop-setup/SKILL.md) | 通过 setup work order 创建受管项目工作流和知识指引；不会创建业务 feature |
| 请求的行为需要一个新的、显式受管的 feature 身份 | [`xc-new-feature`](../../../skills/xc-new-feature/SKILL.md) | 创建 feature 目录，批准 feature 基线，然后实现并验证 feature |
| 已有行为尚未受管，但未来演进需要持久基线 | [`xc-feature-adoption`](../../../skills/xc-feature-adoption/SKILL.md) | 根据当前代码和测试证据推导并批准基线，不改变产品行为 |
| 只需确定事实或影响，不要求产品变更 | [`xc-work`](../../../skills/xc-work/SKILL.md) 配合 `mode=investigation` | 产出证据和结果；可以省略方案、实现和验证 |
| 需要修改已有代码、配置或行为 | `xc-work` 配合 `mode=change` | 按需选择分析、方案、实现和验证阶段 |
| 需要修复已报告的故障 | `xc-work` 配合 `mode=repair` | 根因不确定时先诊断，再返回已批准的变更路径 |
| 需要只读评估文档、代码或证据 | `xc-work` 配合 `mode=review` | 生成分析和评审 artifact，不修改被评审输入 |
| 不创建 feature 的日常维护 | `xc-work` 配合 `mode=maintenance` | 只运行维护目标所需的文档和执行节点 |
| 需要修改可移植工作流契约、项目桥接指引、agent、导出物或编排模板 | [`xc-workflow-evolution`](../../../skills/xc-workflow-evolution/SKILL.md) | 用标准 work order 和评审纪律维护工作流 |

## Direct 或受管治理

在执行实质操作前，应根据宿主和安全规则、用户明确请求、适用项目 bridge、公开 Skill 契约及可观察任务事实，确认以下六项事实。每项值只能是 `no`、`yes` 或 `unknown`。

| 事实 | 何时使用 `yes` | 仅在何时使用 `no` |
| --- | --- | --- |
| `needs_persistence` | 正确完成要求写入或保留项目或外部状态、持久文档、可恢复进度，或当前回复之后仍可用的证据 | 不写任何持久状态，且结果只在当前交互中使用 |
| `material_impact` | 工作会改变共享代码、公开契约、用户数据、权限、生产或基础设施状态、安全边界或发布资产 | 工作为只读，或是不具备上述影响的隔离临时转换 |
| `difficult_rollback` | 没有已确认、已验证、无损的一步恢复方式，或存在不可逆外部副作用 | 工作为只读，或已确认可通过一个确定性步骤完整恢复 |
| `crosses_sessions` | 完成要求后续会话、重启、定时等待、异步外部结果或跨运行恢复 | 输入齐备，可以连续执行一次完成，且不需等待或续跑 |
| `multiple_actors` | 至少两个独立的人、agent、审批者或外部系统负责协调的决定或交付物 | 由单一执行者负责，且没有审批、移交或并行依赖 |
| `audit_required` | 用户、法律、项目 bridge、Skill 或工作流契约要求保留可追踪记录、批准、验证、审查或 commit | 已读取适用政策，并确认这些要求均不存在 |

证据不足以支持 `yes` 或 `no` 时（包括无法消解的冲突）应使用 `unknown`。只有全 `no` 向量允许 direct；任一 `yes` 或 `unknown` 都选择受管工作，已显式选择的受管执行绝不会自动降级。

确认向量前必须读取适用项目 bridge。它可以把 `no` 收紧为 `unknown` 或 `yes`，也可以把 `unknown` 收紧为 `yes`；不能把 `yes` 或 `unknown` 放宽为 `no`，也不能把 `yes` 改为 `unknown`。预期存在项目上下文但 bridge 或适用规则不可用时，至少应把 `audit_required` 设为 `unknown`。

## 分类边界

应使用可执行的公开 [`xc-work operation=classify`](../../../skills/xc-work/SKILL.md) 边界：

```console
python skills/xc-work/scripts/classify.py [--needs-persistence no|yes|unknown] [--material-impact no|yes|unknown] [--difficult-rollback no|yes|unknown] [--crosses-sessions no|yes|unknown] [--multiple-actors no|yes|unknown] [--audit-required no|yes|unknown]
```

适配器允许每项事实省略，将缺失项补为 `unknown`，调用并校验严格低层分类器，而且始终成功退出。畸形、重复或矛盾输入、可执行文件缺失、超时或非零退出、JSON 畸形以及未知 schema/route 都会产生 `route=managed`、`classification_status=escalated` 和原因 `classification-unavailable`。低层分类器仍要求六项事实各准确提供一次，并保留非零诊断错误；它不是公开生命周期命令。

适配器只验证事实和可观察的子进程输出，不认证调用方、Python 解释器、可执行文件字节或宿主，也不提供宿主中介或证明。分类本身不会创建 workshop、work order、文档、运行时树、artifact 或 commit。

示例：

- 只修正临时文本中的一个拼写、不写文件也不保留证据时，如果六项均已确认为 `no`，可以保持 direct。
- 解释已提供的代码片段也可遵循同一全 `no` 规则保持 direct；显式选择 `operation=run` 仍会启动受管工作。
- Direct 调查发现需要跨会话追踪后，必须在下一项实质操作前停止，并携带原请求、已完成动作和当前证据进入 `xc-work operation=run`。
- 凭据轮换或破坏性命令即使很短，只要实质影响或回滚事实为 `yes` 或 `unknown`，就必须立即进入受管工作；请求长度不会降低治理要求。

更强的模型可以在 direct 路径的一个主会话中保留更多推理，也可以在选定路径后减少不必要的委派。它不能改变已确认事实、绕过受管控制、削弱 artifact 或验证，也不能用完整树访问替代限定范围的 control packet。治理没有模型专用 profile。

名为 `context_bytes` 的工作流测量统计归一化 UTF-8 运行时协议 payload 的字节数。它不是 token 数、模型时延、执行时延、成本或质量指标。

## 选择规则

如果必需的 workshop 桥接尚不存在，应先执行 setup，再进入其他生命周期。Setup 会询问项目事实，不会自行编造命令、约定或知识源。

只有产品需要新的受管 feature 身份时才使用 new-feature。如果行为已经存在，目标是把它纳入受管基线，应使用 adoption。如果 feature 已经受管，应使用普通 work order 并提供已有 feature ID。

普通 work order 适用于可能关联零个、一个或多个已有 feature 的持久工作。先依据目标结果选择模式，再由证据决定需要哪些可选文档和节点。根因已知的修复无需重复不必要的诊断；根因不确定时，在修复前使用[诊断契约](../../../skills/xc-diagnosis/SKILL.md)。

当变更对象是 XC 自身或项目的受管桥接时，使用 workflow evolution。它通过 `scope` 区分 `portable-core`、`project-bridge`、`agent-export`、`orchestration-template` 和 `health-check` 工作，避免混合通用关注点与项目专属关注点。

## 服务不是生命周期入口

[`xc-open-work-order`](../../../skills/xc-open-work-order/SKILL.md)为调用方创建持久 workbench，但不能替代生命周期选择。分析、澄清、实现、验证、评审、文档演进和编排 Skill 同样是由所选生命周期调用的有界能力。
