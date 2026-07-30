# 实现与质量

**语言：** [English (英文)](../../../reference/skills/implementation-and-quality.md) | **简体中文 (Simplified Chinese)**

这些支撑 Skill 执行获批变更并评估其证据。

## `xc-implementation`

[规范契约](../../../../skills/xc-implementation/SKILL.md)

- **何时调用：** 获批方案和必需门禁已经确定一个有边界的实现变更时。
- **用途：** 只执行一个 runtime 实现节点，并记录变更路径、验证、基线影响和残余风险。
- **公开入口：** 必填 `workbench_path`、`work_scope`、`inputs` 和 `artifact_path`。
- **典型用法：** 阅读节点契约和获批输入，实施最小完整变更，运行局部检查并写入声明的 artifact。
- **主要边界：** 不负责分解或重试，不得顺手覆盖功能基线，只能通过运行时公开命令报告。

## `xc-review`

[规范契约](../../../../skills/xc-review/SKILL.md)

- **何时调用：** 工作流需要独立评估受管文档、方案、代码变更、诊断或验证证据时。
- **用途：** 评估不可变输入，产出可追踪、按严重度排序的 findings 和结论。
- **公开入口：** 必填 `review_kind`、`inputs`、`artifact_path`；可选 `review_context`。
- **典型用法：** 检查请求的质量维度，让每个必修 finding 都有证据，并写入已验证 node artifact。
- **主要边界：** 审查对被审对象只读；调用方负责整改和风险决策，原始命令记录不是默认 artifact。

## `xc-verification`

[规范契约](../../../../skills/xc-verification/SKILL.md)

- **何时调用：** 实现、诊断、采用或功能基线需要项目定义的验证证据时。
- **用途：** 运行最小充分命令集，把证据映射到验收条件，并记录结果和覆盖缺口。
- **公开入口：** 必填 `workbench_path`、`verification_scope`、`artifact_path`；可选 `inputs`。
- **典型用法：** 读取项目验证政策，先运行局部检查，再按风险扩展回归检查，并记录每条命令及未执行前置条件。
- **主要边界：** 不编造命令或通过标准，不静默弱化验收条件，也不为强行通过而修改产品行为。
