# 调查与决策

**语言：** [English](../../../reference/skills/investigation-and-decisions.md) | **简体中文**

这些支撑 Skill 在实现前收集证据或解决决策。

## `xc-analysis`

[规范契约](../../../../skills/xc-analysis/SKILL.md)

- **何时调用：** 受管工作订单需要事实、影响分析、对账、诊断支持、方案比较或审查支持时。
- **用途：** 产出证据 artifact，并将获接受的事实、假设、风险、备选方案和未知项综合到工作订单分析中。
- **公开入口：** 必填 `workbench_path` 和 `analysis_scope`；可选 `feature_ids` 和 `inputs`。
- **典型用法：** 调度相互独立的证据视角，再通过文档演进子树进行综合。
- **主要边界：** 分析不修改产品代码或功能基线；不得静默合并无依据主张或冲突证据。

## `xc-clarify`

[规范契约](../../../../skills/xc-clarify/SKILL.md)

- **何时调用：** 证据仍留下由人决定的关键问题，或用户要求澄清、质疑请求或方案时。
- **用途：** 以 `discover` 或 `challenge` 模式运行有边界、可追踪且每次只处理一个决策的门禁序列。
- **公开入口：** 必填 `workbench_path`、`mode`、`subject`、`instance_id`；可选 `inputs` 和 `initial_decision_budget`。
- **典型用法：** 将模板嵌入现有生命周期，先取证，把完整回答写入单一 session artifact，再将决策交回分析与方案选择。
- **主要边界：** 它不是独立工作订单，也不替代取证、审查、方案批准或验证；长内容不得放入 blackboard。

## `xc-diagnosis`

[规范契约](../../../../skills/xc-diagnosis/SKILL.md)

- **何时调用：** 报告问题的根因、失效模式或修复方向尚不确定时。
- **用途：** 复现问题、收集有边界的证据，并记录已确认或疑似原因及修复方向，但不实施修复。
- **公开入口：** 必填 `workbench_path` 和 `problem_statement`；可选 `mode`（`diagnose` 或 `verify`）和 `inputs`。
- **典型用法：** 使用项目定义命令复现，检查代码和运行证据，再把充分结论交回普通 repair 生命周期。
- **主要边界：** 疑似原因必须保留标签；不安全外部访问或破坏性复现会阻塞工作，临时插桩必须获授权并移除。
