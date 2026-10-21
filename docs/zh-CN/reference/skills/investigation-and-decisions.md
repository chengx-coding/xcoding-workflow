# 调查与决策

**语言：** [English](../../../reference/skills/investigation-and-decisions.md) | **简体中文**

这些支撑 Skill 在实现前收集证据或解决决策。

## `xc-conventions`

[规范契约](../../../../skills/xc-conventions/SKILL.md)

- **何时调用：** 即将进行实质性变更时，用于发现存在于项目中、但不在 bridge 内的项目自有开发规范。
- **用途：** 按比例分三级做约定发现：直达路径的 L0 触发线、准备阶段强制的 L1 扫描、以及 L2 重度研读。
- **公开入口：** 必填 `project_root` 和 `tier`（`l0-tripwire`、`l1-scan`、`l2-study`）；可选 `targets`、`bridge_locations`、`workbench_path`。
- **典型用法：** 确定性脚本枚举并分级候选（C1 声明性指令文件、C2 配置性的格式化/lint/CI 信号）；Agent 读取适用的 C1 规则，并把一份紧凑的发现记录路由进实现与验证的 inputs。
- **主要边界：** L1 是独立于可裁剪 analysis 阶段的地板；检查必须留痕（`found` 或 `not-applicable`），扫描失败 fail-closed；未成文的 de-facto 模式只是需标注的弱推断；该 Skill 不连接知识库，也不解析规则语义。

## `xc-analysis`

[规范契约](../../../../skills/xc-analysis/SKILL.md)

- **何时调用：** 受管工作订单需要事实、影响分析、对账、诊断支持、方案比较或审查支持时。
- **用途：** 产出证据 artifact，并将获接受的事实、假设、风险、备选方案和未知项综合到工作订单分析中。
- **公开入口：** 必填 `workbench_path` 和 `analysis_scope`（`investigation`、`reconciliation`、`diagnosis-support`、`solution-support`、`review-support` 或 `convention-review`）；可选 `feature_ids` 和 `inputs`。
- **典型用法：** 调度相互独立的证据视角，再通过文档演进子树进行综合。
- **主要边界：** 分析不修改产品代码或功能基线；不得静默合并无依据主张或冲突证据。

## `xc-clarify`

[规范契约](../../../../skills/xc-clarify/SKILL.md)

- **何时调用：** 证据仍留下由人决定的关键问题，或用户要求澄清、质疑请求或方案时。
- **用途：** 以 `discover` 或 `challenge` 模式运行有边界、可追踪且每次只处理一个决策的门禁序列。
- **公开入口：** 必填 `workbench_path`、`mode`、`subject`、`instance_id`；可选 `inputs` 和 `initial_decision_budget`。
- **典型用法：** 将模板嵌入现有生命周期，先取证，把完整回答写入单一 session artifact，再将决策交回分析与方案选择。
- **主要边界：** 它不是独立工作订单，也不替代取证、审查、方案批准或验证；长内容不得放入 blackboard。

## `xc-deliberate`

[规范契约](../../../../skills/xc-deliberate/SKILL.md)

- **何时调用：** 用户在既有受管工作订单中明确要求就某份文档、某个子问题展开辩论、压力测试或被反驳时。只有用户可以启用；工作流从不自行判定某个主题需要辩论。
- **用途：** 运行由用户主导的辩论：独立的辩驳方攻击用户的推理，用户保留执笔与决策权；随后记录各轮，并把用户确认过的结论合并进它所依据的文档。
- **公开入口：** 必填 `workbench_path`、`scope_document`、`scope_question`、`instance_id`；可选 `inputs` 和 `rebuttals_per_round`（1 到 8，默认 3）。
- **典型用法：** 发布作用域与源文档哈希，在运行时新建的容器里把辩论模板挂载到辩论应当发生的位置；每轮由计划、并行辩驳、独立汇总和一个结构化用户门禁组成；该门禁之后才决定再开一轮还是结束；每满五轮由一名独立工作者给出收敛判断，它不结束任何东西。
- **主要边界：** 它是嵌入式子树，不是工作订单；不替代分析、澄清、审查、实现或验证；结论在用户确认结束并执行合并之前保持为独立文档；逐轮原文可以存在于工作坊内，但不得被公开文档引用。

## `xc-diagnosis`

[规范契约](../../../../skills/xc-diagnosis/SKILL.md)

- **何时调用：** 报告问题的根因、失效模式或修复方向尚不确定时。
- **用途：** 复现问题、收集有边界的证据，并记录已确认或疑似原因及修复方向，但不实施修复。
- **公开入口：** 必填 `workbench_path` 和 `problem_statement`；可选 `mode`（`diagnose` 或 `verify`）和 `inputs`。
- **典型用法：** 使用项目定义命令复现，检查代码和运行证据，再把充分结论交回普通 repair 生命周期。
- **主要边界：** 疑似原因必须保留标签；不安全外部访问或破坏性复现会阻塞工作，临时插桩必须获授权并移除。
