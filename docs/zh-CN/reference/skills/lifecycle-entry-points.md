# 生命周期入口

**语言：** [English](../../../reference/skills/lifecycle-entry-points.md) | **简体中文**

这些 Skill 用于选择并治理完整工作流生命周期。

## `xc-workshop-setup`

[规范契约](../../../../skills/xc-workshop-setup/SKILL.md)

- **何时调用：** 项目首次采用 XC，或缺少必需的 workshop 文档时。
- **用途：** 建立受管的 `.xcoding/WORKFLOW.md` 和 `.xcoding/KNOWLEDGE.md`，但不创建业务功能。
- **公开入口：** 必填 `workshop_path`；可选 `project_root` 和 `auto_commit`。
- **典型用法：** 开启 setup 工作订单，演进并验证两份 workshop 文档，再将其作为 workshop artifact 完成。
- **主要边界：** 不得编造项目事实；通过文档服务验证文档，只能通过公开运行时命令访问运行时状态。

## `xc-open-work-order`

[规范契约](../../../../skills/xc-open-work-order/SKILL.md)

- **何时调用：** 生命周期需要持久工作订单 ID、runtime 路径和 artifacts 路径时。
- **用途：** 验证 workshop 隔离，并创建标准的 `artifacts/` 与 `runtime/` 工作台目录。
- **公开入口：** `open_work_order.py`，必填 `workshop_path`；可选 `project_root`、`topic`、`work_order_id` 和重复的 `feature_ids`。
- **典型用法：** 在初始化运行时前调用，并直接使用 JSON 返回的绝对路径。
- **主要边界：** 不创建文档、运行时树、功能目录、日志或 Git commit；调用方不得自行重建返回路径。

## `xc-work`

[规范契约](../../../../skills/xc-work/SKILL.md)

- **何时调用：** 持久调查、变更、修复、审查、维护或跨功能工作涉及零个或多个现有功能时。
- **用途：** 运行普通工作订单生命周期，并仅启用所选模式需要的分析、方案、实现和验证阶段。
- **公开入口：** 必填 `workshop_path`、`project_root`、`request`；可选 `feature_ids`、`mode` 和 `document_language`。
- **典型用法：** 创建目标，按需对账现有功能，澄清关键决策，批准方案，执行实现和验证，最后写结果。
- **主要边界：** 不得隐式创建或采用功能；动态状态留在运行时树中，文档语言由发起请求固定，除非用户明确纠正。

## `xc-new-feature`

[规范契约](../../../../skills/xc-new-feature/SKILL.md)

- **何时调用：** 请求行为需要一个新的、明确受管的功能时。
- **用途：** 创建功能目录，批准三份持久基线，并在一个工作订单内治理实现和验证。
- **公开入口：** 必填 `workshop_path`、`project_root`、`feature_id`、`request`；可选 `auto_commit` 和 `document_language`。
- **典型用法：** 初始化功能，演进目标和基线文档，通过批准门禁，再添加有边界的实现与验证节点。
- **主要边界：** 基线批准前不得实现；功能文档必须通过文档演进处理，动态状态不得写入 `tasks.md` 或 `status.md`。

## `xc-feature-adoption`

[规范契约](../../../../skills/xc-feature-adoption/SKILL.md)

- **何时调用：** 现有未受管或手工开发的功能需要持久受管基线时。
- **用途：** 从代码和可执行测试证据推导获批功能基线，不改变产品行为。
- **公开入口：** 必填 `workshop_path`、`project_root`、`feature_id`、`code_entry`；可选 `request` 和 `document_language`。
- **典型用法：** 分析现有实现，起草三份功能基线，明确不确定性，并取得显式基线批准。
- **主要边界：** 采用不是修复或增强；没有证据和确认，当前行为不得转化为目标意图。

## `xc-workflow-evolution`

[规范契约](../../../../skills/xc-workflow-evolution/SKILL.md)

- **何时调用：** 需要审慎变更可移植工作流契约、模板、agent、导出、项目 bridge 指引或健康检查时。
- **用途：** 将普通工作订单和审查纪律用于工作流维护，同时区分可移植核心与项目专属政策。
- **公开入口：** 必填 `scope`、`workshop_path`、`request`；`scope` 选择 portable core、project bridge、agent export、orchestration template 或 health check。
- **典型用法：** 开启零功能工作订单，记录分析和方案，修改规范源，按需重新生成受管输出，并验证受影响接口。
- **主要边界：** 不得手工修改生成资产或受管运行时状态；广泛架构变更需要备选方案、审查和显式用户门禁。
