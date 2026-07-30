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

## 选择规则

如果必需的 workshop 桥接尚不存在，应先执行 setup，再进入其他生命周期。Setup 会询问项目事实，不会自行编造命令、约定或知识源。

只有产品需要新的受管 feature 身份时才使用 new-feature。如果行为已经存在，目标是把它纳入受管基线，应使用 adoption。如果 feature 已经受管，应使用普通 work order 并提供已有 feature ID。

普通 work order 适用于可能关联零个、一个或多个已有 feature 的持久工作。先依据目标结果选择模式，再由证据决定需要哪些可选文档和节点。根因已知的修复无需重复不必要的诊断；根因不确定时，在修复前使用[诊断契约](../../../skills/xc-diagnosis/SKILL.md)。

当变更对象是 XC 自身或项目的受管桥接时，使用 workflow evolution。它通过 `scope` 区分 `portable-core`、`project-bridge`、`agent-export`、`orchestration-template` 和 `health-check` 工作，避免混合通用关注点与项目专属关注点。

## 服务不是生命周期入口

[`xc-open-work-order`](../../../skills/xc-open-work-order/SKILL.md)为调用方创建持久 workbench，但不能替代生命周期选择。分析、澄清、实现、验证、评审、文档演进和编排 Skill 同样是由所选生命周期调用的有界能力。
