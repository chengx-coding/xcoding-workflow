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

- **何时调用：** 需要选择治理方式或成比例的受管投入，或持久调查、变更、修复、审查、维护或跨功能工作涉及零个或多个现有功能时。
- **用途：** 提供 direct-versus-managed 分类、确定性 capability planning、兼容的完整生命周期，以及显式的最小自适应受管生命周期。
- **公开入口：** `operation=run|classify|plan|adaptive-run`，默认为 `run`，并必填 `request`。`run` 与 `adaptive-run` 要求 `workshop_path` 和 `project_root`。`plan` 接受治理、bridge policy、范围、清晰度、风险、验证、协作、持续时间、审计、pace 和 mode 事实。
- **分类：** 执行 `python skills/xc-work/scripts/classify.py [事实参数]`。只有六项已确认的 `no` 才返回 direct；任一 `yes` 或 `unknown` 都返回 managed。省略事实会变成 `unknown`；非法输入、可执行文件缺失、超时、低层非零退出、JSON 畸形或未知 schema/route 都会以零状态退出，并返回带 `classification_status=escalated` 和原因 `classification-unavailable` 的 managed 结果。
- **规划：** 执行 `python skills/xc-work/scripts/plan_work.py [规划事实]`。Plan 会单调推导文档、分析、gate、implementation unit、verification scope、review、recovery、depth，以及绑定 request/bridge 的 plan receipt。非法或伪造输出会 fail closed 到完整安全 capability 集合。
- **典型受管用法：** 省略 `operation` 或使用 `operation=run` 保持现有完整生命周期。显式使用 `adaptive-run` 时，root 下只有 sequence dynamic group；最小形态包含一个 combined work leaf 和一个 finalizer，其他 capability 只在事实要求时增加。
- **主要边界：** 分类只读且不执行实质操作。公开适配器会验证可观察的子进程结果，但不认证调用方、解释器、可执行文件字节或宿主，也不提供宿主中介或证明。严格低层分类器保留非零诊断错误，但不是生命周期入口。受管工作不得隐式创建或采用功能。

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
- **公开入口：** 必填 `scope`、`workshop_path`、`project_root` 和 `request`；`scope` 选择 portable core、project bridge、agent export、orchestration template 或 health check。
- **典型用法：** 确认六项治理事实，调用公开 `xc-work operation=classify`，然后只执行全 `no` 所允许的当前响应内动作，或以零 feature 进入公开 `xc-work operation=run`。受管工作会记录分析和方案、修改规范源、按需重新生成受管输出并验证受影响接口。
- **主要边界：** 只依赖 `xc-work` Skill 名称和公开参数，不调用另一个 Skill 的私有分类脚本或 reference。不得手工修改生成资产或受管运行时状态；广泛架构变更需要备选方案、审查和显式用户门禁。
