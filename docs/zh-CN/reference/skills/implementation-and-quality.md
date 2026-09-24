# 实现与质量

**语言：** [English](../../../reference/skills/implementation-and-quality.md) | **简体中文**

这些支撑 Skill 执行获批变更、向人类评审者解释变更，并评估其证据。

## `xc-change-report`

[规范契约](../../../../skills/xc-change-report/SKILL.md)

- **何时调用：** 工单改动了可分析代码，且人类必须在不打开 IDE 的情况下评审这些改动时：在实现与验证之后、结果文档之前。
- **用途：** 把单个工单的变更集合产出为一个离线自包含 HTML 报告，以及一份覆盖清单：清单证明每个可分析变更单元都有分析覆盖，分析与所引用代码绑定，并说明改了什么、为什么存在、体现了什么设计、处于更大流程的哪一环。单元还可以额外声明变更分类，并回答该分类要求的设计维度（动机、变更前后、替代方案、生命周期、上游调用方与下游被调用方、取舍、影响），并携带结构化深度块（变更前后步骤表、生命周期表或调用方/被调用方表），使报告能自顶向下地从设计意图讲到具体实现；这些维度只做存在性与结构性校验，不判断内容正确性。遵循优先图示的默认原则，调用方/被调用方与变更前后的深度块还会自动派生分层调用图与前后流程图，序列交互可选用确定性 SVG 载体，而对'最佳表达为图却未配图'的变更分类只产出非阻塞建议、不判失败。
- **公开入口：** 必填 `report_path`、`manifest_path`、`repo_path`、`baseline_commit`、`language`、`strength`；校验还必填 `stage`，`verdicts_path` 只在 final 阶段必填；`gate_required` 默认 `false`。两个基线快照目录 `baseline_worktree_dir` 与 `baseline_untracked_dir` 实际上是必需的，因为校验器要从已记录的快照、而不是从当前工作树重新计算基线 digest。包自带的采集命令负责产出它们：`python skills/xc-change-report/scripts/capture_baseline.py --repo <repo> --workbench <workbench> --work-order-id <id> [--baseline-worktree-dir <dir>] [--baseline-untracked-dir <dir>] [--format json|keys]`，它的第二种 `--verify-existing` 形态会从已记录的工作树快照重新计算已记录的 digest，把已记录的计数与 git 及这两个已记录快照重新核对，任一处不匹配都会关闭失败，且不会再次生成这两个目录。
- **典型用法：** 在工作树仍处于打开状态、实现尚未触碰它之前采集基线：在打开 work order 时运行采集形态一次，它把已跟踪路径镜像到 `<workbench>/tmp/baseline-worktree/`，把未跟踪路径镜像到 `<workbench>/tmp/baseline-untracked/`，并把这两个目录与工作树 digest 一起记录到 `<workbench>/tmp/baseline-open-state.json`。然后枚举变更集合并发布清单，生成骨架，为清单中的每个单元写入八个必需的分析字段（多个单元可以共用一段分析，只要该段声明覆盖它们的全部锚点），最后在准确性复核前后分别以 `stage=coverage` 与 `stage=final` 校验。每一轮都重新生成同一个报告；代码返工导致报告过期时走刷新，而不是判为节点失败，且刷新循环有界。
- **主要边界：** 从不修改代码，也不对变更作出验收结论；强度档位只改变内容厚度，因为三档都必须运行全部机械校验与准确性复核；人类门禁可选且默认关闭；哈希与令牌校验只证明分析与所引用代码绑定，不证明分析正确，而判断含义的准确性复核本身也可能出错。

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
- **典型用法：** 阅读节点契约和获批输入，实施最小完整变更，运行局部检查并写入声明的 artifact。自适应 minimal 节点可以在验证不可变 plan receipt 后，把一个 coherent implementation 与 focused verification 合并执行。
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
- **典型用法：** 读取项目验证政策，先运行局部检查，再按风险扩展回归检查，并记录每条命令及未执行前置条件。Adaptive regression 或 multi-environment scope 使用独立验证节点；fast pace 不能删除 required scope。
- **主要边界：** 不编造命令或通过标准，不静默弱化验收条件，也不为强行通过而修改产品行为。
