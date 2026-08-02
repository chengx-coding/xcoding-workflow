**语言：** [English](../../workflows/running.md) | **简体中文**

# 运行受管工作

受管生命周期把决策与证据持久保存在文档和 artifact 中，由编排运行时负责执行状态。具体路径由入口工作流和已接受方案决定；可选阶段不会仅为了填满模板而加入。

## 生命周期

1. **加载项目策略。** 在选择命令或作出项目专属假设前，读取项目指引、workshop 桥接和已声明的知识指引。
2. **打开并初始化 work order。** 创建持久 workbench，初始化受管树，并在写入第一份顶层文档前固定 work order 文档语言。
3. **记录目标。** `goal.md` 定义请求结果、边界、约束和验收方向。
4. **建立证据。** 需要事实、影响、备选方案、诊断或 feature 协调时，[`xc-analysis`](../../../skills/xc-analysis/SKILL.md)把不同视角的证据记录到节点 artifact，并将接受的事实综合到 `analysis.md`。
5. **澄清人类决策。** 当证据无法回答重要决策时，[`xc-clarify`](../../../skills/xc-clarify/SKILL.md)在方案选择前通过主会话 gate 提出有界问题。它不能代替调查。
6. **选择并批准方案。** `solution.md` 记录选定变更、边界、风险、兼容性影响和验证策略。重要决策和未解决风险必须经过显式用户 gate。
7. **执行有界实现节点。** 每个 [`xc-implementation`](../../../skills/xc-implementation/SKILL.md) worker 只接收一个已批准范围，只修改归其所有的文件，记录证据，并通过运行时报告结果。
8. **验证与评审。** [`xc-verification`](../../../skills/xc-verification/SKILL.md)运行项目定义的检查并记录覆盖缺口。需要独立质量评估时，[`xc-review`](../../../skills/xc-review/SKILL.md)评估不可变输入并产出可追踪 finding。失败证据会返回所属生命周期处理，而不是静默降低验收标准。
9. **形成结果并关闭。** `result.md` 在 work order 最终完成前汇总已交付行为、验证、未解决风险和相关 artifact。

顶层 work order 文档是持久记录，不是程序计数器。动态顺序、就绪状态、循环、重试、blocker 和进度都留在运行时树中。

## 执行边界

主会话向[编排运行时](../../../skills/xc-orchestration-runtime/SKILL.md)请求下一个就绪节点或批次。对于已 opt-in 的叶子节点，调度顺序是 `next -> control-packet --node <id> -> start`。主会话必须在启动或委派节点前读取 packet，处理用户 gate，并在 worker 返回后核对状态。

每个 worker 只执行 packet 中的一个 target 节点。它只读取已提供的输入和 reference，写入已声明的 artifact，然后调用 `complete`、`fail` 或 `block`。Worker 不会检查完整树、执行兄弟节点、把 source ID 当作启动其他节点的权限，也不会决定下一次全局转换。

长篇报告、diff 和日志属于 artifact。Blackboard 只保存影响后续调度或决策的短结构化值。

## 限定范围的交接

叶子节点声明领域命名的来源类别、来源及 artifact 阈值，以及允许投影的 blackboard 键。直接的 `node:` selector 标识一个来源；`bb:` selector 读取一个由终态 runtime 叶子 ID 组成的紧凑 UTF-8 JSON 数组，例如 `["rt_source_a","rt_source_b"]`。它不是 CSV、通配符或权限列表。生命周期调用方必须在请求 packet 前发布真实终态来源 ID，绝不能用 ancestor 或 group ID 替代。

Packet 只包含 target 叶子契约、已声明的来源结果字段与 artifact、选定的 blackboard 标量、局部 readiness blocker 和允许的控制动作。它不继承 ancestor 声明，也不暴露未声明的 sibling 或 future-node 数据、来源 instructions、未声明 artifact、未选择的 blackboard 键、完整 blackboard 或完整树。Source ID 只允许投影证据，不授予控制该来源或任何其他节点的权限。

这个边界限制的是运行时协议披露，不是宿主 mediation。Runtime 无法阻止 agent 在 `start` 前使用普通宿主工具，也不能强制验证实际调用 CLI 的身份；这些边界必须由宿主和调用 Skill 执行。

## 完成与 Gate

Opt-in completion metadata 可以要求非空 `summary` 或 `validation`、artifact 数量上下界、与 literal 或 blackboard selector 完全相同的 artifact 路径，以及已声明的归一化 check receipt。`complete` 通过可重复的 `--check-result-json` 接收每个已声明 check 的 receipt。Receipt 的精确形状是 `{"schema_version":1,"check":"...","ok":true,"subject":"...","facts":{...}}`；runtime 会验证其形状、已声明名称、`ok`、subject 和 fact 值，并且只保存归一化 receipt。

调用方必须实际运行已声明 validator，要求进程退出成功且顶层结果成功，并只提取其归一化 receipt。即便如此，receipt 仍是未签名、未绑定 claimant 的调用方自报告；它既不能证明验证确实运行过，也不能证明运行者身份。完全匹配已声明结构和预期值的伪造 receipt 会被接受。Runtime 检查提高的是结果一致性，不会建立 trusted execution。

Opt-in structured gate 会声明允许的 lowercase-kebab outcome、是否要求非空 decision，以及可选的 outcome blackboard key。主会话通过 `--gate-outcome` 和按需提供的 `--decision` 完成 gate；结果与可选 blackboard 写入是原子操作。没有这些声明的 legacy gate 保持原有完成行为。

Runtime 会验证并发布 outcome，但不会根据字符串拼写赋予领域接受语义。因此，当前生命周期模板通过 fail-closed 拓扑路由已发布值：接受结果选择正常后续路径；拒绝、需要修订、尚未解决的澄清，或 reconciliation 的 `revise-goal` 结果都会暴露一个开放 recovery group，并阻止实现、验证、最终文档校验、结果写入或最终完成。Recovery group 中的修订工作和后继 gate 必须先发布接受值，流程才能继续。被跳过的可选 gate 使用所属模板显式声明的安全默认值，而不是空 outcome。

## 恢复工作

使用已有树引用，通过运行时公开命令恢复执行。`next`、`summary`、`show` 和 `find` 无需直接访问受管存储即可向主会话暴露所需状态。调用方使用运行时返回的路径和节点 ID，不自行重建。

如果一个开放且可达的 dynamic group 没有子节点，运行时会报告它正在等待工作。主会话必须加入已批准节点或显式关闭该 group；就绪列表为空不自动等同于死锁。

成功完成的树会被封存。增加工作需要用户明确批准理由并调用运行时 reopen 操作；普通执行不会向已封存的历史树追加节点。

## 失败与恢复

- 节点已尝试执行但无法满足契约时使用 `fail`。保留证据，由所属生命周期决定重试、修订或选择其他路径。
- 进度依赖用户输入、外部访问、安全复现前提或其他可恢复条件时使用 `block`。
- 把验证失败当作工作流结果。不能仅为了通过而在验证节点中修改行为或验收标准。
- 状态冲突、树已封存响应和完整性失败应报告给主会话，不能重试含义不明的状态变更。
- 使用运行时诊断和显式完整性修复操作，绝不直接修补 checksum 或状态字段。

启用运行时 checkpoint commit 时，终态转换及已声明的 workshop artifact 会按路径限定范围。Checkpoint 失败会回滚树状态转换，因此未提交的持久化错误不能被报告为成功完成。
