# 实现与质量

**语言：** [English](../../../reference/skills/implementation-and-quality.md) | **简体中文**

这些支撑 Skill 执行获批变更、指导技术写作并评估证据。

## `xc-delegation`

[规范契约](../../../../skills/xc-delegation/SKILL.md)

- **何时调用：** Skill 通过持久 delegated Agent 委派一个私有 worker 角色，需要严格 profile 解析、能力收窄、确定性准备或只读 legacy 发现时。
- **用途：** 校验 Skill 内部 worker profile，并为一个节点 attempt 编译 dispatch envelope，而不把私有角色变成持久 Agent。
- **公开入口：** 必填 `skill_root` 与 `profile_id`；prepare 还需要精确 runtime node/profile packet、项目 policy、调用方约束、adapter ID 和输出路径。Dynamic overlay 可选且只能收窄。
- **典型用法：** 在所属 Skill 的 `assets/workers/` 下编写 profile，完成校验，取得精确运行中 attempt 的 assignment wrapper，调用 `xcoding delegate prepare`，并且只 dispatch authoritative envelope。
- **主要边界：** v1 不会静默回退到 legacy prompt；能力层只能收窄；runtime 状态与 terminal authority 仍由 runtime 拥有；当前宿主声明在没有固定版本端到端证据时不声称 enforcement。

## `xc-implementation`

[规范契约](../../../../skills/xc-implementation/SKILL.md)

- **何时调用：** 获批方案和必需门禁已经确定一个有边界的实现变更时。
- **用途：** 只执行一个 runtime 实现节点，并记录变更路径、验证、基线影响和残余风险。
- **公开入口：** 必填 `workbench_path`、`work_scope`、`inputs` 和 `artifact_path`。
- **典型用法：** 阅读节点契约和获批输入，按任务采用最小充分幅度实现已批准范围（`create` 在质量契约内最大化，`change` 用最小充分改动，`repair` 保持强最小性预设），运行局部检查并写入声明的 artifact。对 `create`，accepted capability matrix 是已批准范围的一部分：实现每个 accepted must capability，不得静默丢弃或削弱 must/should capability；范围或 must capability 不足时停下返回调用方，而不是自行扩缩。自适应 minimal 节点可以在验证不可变 plan receipt 后，把一个 coherent implementation 与 focused verification 合并执行。
- **主要边界：** 不负责分解或重试，不得顺手覆盖功能基线，只能通过运行时公开命令报告。范围的扩大或缩小是调用方或 gate 的决定，不是 worker 的决定。

## `xc-visual-design`

[规范契约](../../../../skills/xc-visual-design/SKILL.md)

- **何时调用：** 视觉质量属于渲染产物验收的一部分，或 project bridge 声明 visual target。
- **用途：** 负责 visual brief 和独立 critic 循环；不拥有风格、palette、评分或功能 capability 清单。
- **公开入口：** `workbench_path`、`brief_path`、`review_path`、`screenshots`；可选 `functional_evidence`。功能 preservation evidence 由 `xc-verification` 拥有。
- **方法边界：** target 来自 request/bridge；不固定视觉维度；必须有独立 critic；未解决 high 或 functional gate 失败阻止接受。

## `xc-writing`

[规范契约](../../../../skills/xc-writing/SKILL.md)

- **何时调用：** 起草面向人的技术回答、解释、文档或报告，修订难懂文字，或在保留原意的前提下评审清晰度时。
- **用途：** 帮助读者理解对象、推理与取舍，同时保留事实、条件、例外、规范强度和不确定性。它统一拥有文档和独立问答的共享写作方法。
- **公开入口：** 必填 `request`；`operation=write|revise|review` 默认 `write`；可选 `inputs`、`audience` 和 `authoring_requirements`。每个输入对象包含 `kind=text|path` 和非空字符串 `value`，不把裸字符串猜成路径；修订和审阅须有可识别的目标文本。
- **典型用法：** 提供当前问题或写作任务及原材料，按读者需要组织解释，再据证据核对结果。例如设置 `operation=revise` 并传入 `inputs=[{"kind":"text","value":"草稿仅作者可见。"}]` 可修订所给文字，而不读取文件。审阅只返回有证据的文字发现及局部建议，不修改原文。
- **主要边界：** 不取代受管文档结构校验、文档生命周期、整体质量评审或调用者授权；材料缺失或含糊时如实报告，不自行编造。用户风格和语言要求适用，命令、证据与关键约束保持准确。不新增持久模式、可读性评分、ISO 符合性声明，也不保证影响所有未来回复或读者。

## `xc-review`

[规范契约](../../../../skills/xc-review/SKILL.md)

- **何时调用：** 工作流需要独立评估受管文档、方案、代码变更、诊断或验证证据时。
- **用途：** 评估不可变输入，产出可追踪、按严重度排序的 findings 和结论。
- **公开入口：** 必填 `review_kind`、`inputs`、`artifact_path`；可选 `review_context`。
- **典型用法：** 检查请求的质量维度，让每个必修 finding 都有证据，并写入已验证 node artifact。 当体验型产品提供 proposed overlay 检查时，包含首次可发现性、`xc-visual-design` 的 review artifacts（视觉质量在验收中时）、状态背景和 progression；不要从单纯的视觉表面推断该 overlay。对 code/solution review 还检查 under-scope（需求或质量 bar 未满足）、over-scope（无谓改动或超出批准范围）和 scope drift（实现与记录的 scope decision 不一致）。对 `create`，对照原始请求加 accepted capability matrix 检查保真，而不只是 approved solution；没有用户/项目来源的 material exclusion 属于无来源缩窄。存在 reference signature 时，缺失或明显削弱的 signature must capability 是 under-scope；signature should capability 也是 under-scope，除非 accepted matrix 记录了带原因和影响的 deferral；导入无关参考 feature 是 over-scope。存在 prior capability inventory 时，无解释的缺失是 finding；replace/retire 需要记录原因、影响和来源，prior should 可带原因、影响、来源和重新进入触发条件而接受为 defer。 对 交互式视觉体验产品，first-run affordance 和 visual-state backdrop 是 visual-row must。
- **主要边界：** 审查对被审对象只读；调用方负责整改和风险决策，原始命令记录不是默认 artifact。范围 finding 是有证据的评审判断，不是机械 scope checker。

## `xc-verification`

[规范契约](../../../../skills/xc-verification/SKILL.md)

- **何时调用：** 实现、诊断、采用或功能基线需要项目定义的验证证据时。
- **用途：** 运行最小充分命令集，把证据映射到验收条件，并记录结果和覆盖缺口。
- **公开入口：** 必填 `workbench_path`、`verification_scope`、`artifact_path`；可选 `inputs`。
- **典型用法：** 读取项目验证政策，先运行局部检查，再按风险扩展回归检查，并记录每条命令及未执行前置条件。对体验型产品，执行首次可发现性、`xc-visual-design` 的 review artifacts（视觉质量在验收中时）、状态背景和 progression 检查。对 `create`，使用 analysis 选择的 output-surface profile，把证据映射到 accepted matrix 中的每个 must/should capability；测试全过不等于未验证 capability 已证明。对视觉表面，使用 visual profile 的 visible-state/multi-state 检查；对 CLI/API/file 或 docs 表面，使用各自证据，不要求截图。Adaptive regression 或 multi-environment scope 使用独立验证节点；fast pace 不能删除 required scope。 对 交互式视觉体验产品，first-run affordance 和 visual-state backdrop 是 visual-row must。
- **主要边界：** 不编造命令或通过标准，不静默弱化验收条件，也不为强行通过而修改产品行为。

## 体验型产品 overlay

`experience-quality` 是 proposed task-class overlay；视觉质量委托给 `xc-visual-design`，功能证据委托给 `xc-verification`；overlay 不拥有风格或通用评分。
