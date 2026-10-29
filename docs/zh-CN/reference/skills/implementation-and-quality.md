# 实现与质量

**语言：** [English](../../../reference/skills/implementation-and-quality.md) | **简体中文**

这些支撑 Skill 执行获批变更、向人类评审者解释变更、指导技术写作并评估证据。

## `xc-change-report`

[规范契约](../../../../skills/xc-change-report/SKILL.md)

- **何时调用：** 工单改动了可分析代码，且人类必须在不打开 IDE 的情况下评审这些改动时：在实现与验证之后、结果文档之前。
- **用途：** 把单个工单的变更集合产出为一个离线自包含 HTML 报告，以及一份覆盖清单：清单证明每个可分析变更单元都有分析覆盖，分析与所引用代码绑定，并说明改了什么、为什么存在、体现了什么设计、处于更大流程的哪一环。单元还可以额外声明变更分类，并回答该分类要求的设计维度（动机、变更前后、替代方案、生命周期、上游调用方与下游被调用方、取舍、影响），并携带结构化深度块（全宽的变更前后步骤对比、生命周期表或调用方/被调用方表），使报告能自顶向下地从宏观设计意图讲到具体实现——各 section 按漏斗排列（概览、架构元素、变更地图索引、逐单元下钻，其中单元按所属元素分组并折叠为细节层），且所有宽表格均不超框；这些维度只做存在性与结构性校验，不判断内容正确性。报告的脊梁是架构元素：一至七个元素，每个元素有六段画像（它是什么、原来怎样运转、现在怎样运转、为什么必须变、承诺与边界、指向细节），元素地图在声明了关系时由这些关系派生，并渲染为标注各元素提供与需要哪些接口的组件图，概览给出三问简报（最坏情况、回滚方式、未验证部分）；每个可分析单元绑定到一个元素或显式的 `mechanical`/`unassigned` 桶，其数量在报告信息节公布。当存在一个仅凭概览、架构元素与单元 section 难以回答、且需要与单元、图表或验证建立明确联系的决策级读者问题时，标准或完整报告可以在架构元素 section 内加入一个可选的设计主题层；该层复用现有锚点，把宏观图示保留在报告级图区，并不改变最小报告。遵循优先图示的默认原则，调用方/被调用方与变更前后的深度块还会自动派生分层调用图与前后流程图；这些单元级图内联渲染在它们所解释的单元内、紧邻其深度块。序列交互可选用确定性 SVG 载体，而对'最佳表达为图却未配图'的变更分类只产出非阻塞建议、不判失败。
- **公开入口：** 必填 `report_path`、`manifest_path`、`repo_path`、`baseline_commit`、`language`、`strength`；校验还必填 `stage`，`verdicts_path` 只在 final 阶段必填；`gate_required` 默认 `false`。两个基线快照目录 `baseline_worktree_dir` 与 `baseline_untracked_dir` 实际上仍然必需，因为校验器要依据已记录的采集范围加上基线提交、而不是依据当前工作树重新计算基线 digest。包自带的采集命令负责产出它们：`python skills/xc-change-report/scripts/capture_baseline.py --repo <repo> --workbench <workbench> --work-order-id <id> [--baseline-worktree-dir <dir>] [--baseline-untracked-dir <dir>] [--format json|keys]`；它的第二种 `--verify-existing` 形态会依据已记录的范围重新计算已记录的 digest，不会再次生成这两个目录，并把已记录的计数与 git 和已记录的快照重新核对，任一处不匹配都会关闭失败。当版本控制无法提供基线一侧时——目录不是工作树、`HEAD` 无法解析，或它解析到的提交工具无法读取——采集会关闭失败、不复制任何内容，并携带底层原因报出具名错误 `baseline_vcs_unavailable`；唯一授权完整复制已跟踪集合的方式是 `--full-tracked-mirror` 加上一个非空、指明用户明确决定的 `--consent-reference`，两者缺一不可，否则不复制任何内容。这样的记录为没有基线提交的树镜像内容：`--verify-existing` 可以重算它的 digest，但无法据此产出经过校验的变更报告。
- **典型用法：** 在工作树仍处于打开状态、实现尚未触碰它之前采集基线：在打开 work order 时运行一次采集形态，它只把开启时与基线提交不同的已跟踪路径镜像到 `<workbench>/tmp/baseline-worktree/`，把未跟踪路径镜像到 `<workbench>/tmp/baseline-untracked/`，并把这两个目录、开启时已脏与开启时已删除的路径名单以及工作树 digest 记录到 `<workbench>/tmp/baseline-open-state.json`；每个开启时干净的已跟踪路径都从基线提交读回，所以 digest 保持原有的取值语义，只有重算来源变为混合；当基线提交已无法提供某个干净路径时，这也不是被静默忽略的缺口：校验器的 digest 重算会以具名错误 `baseline_worktree_snapshot_commit_unavailable` 失败，而不是把该证明当作完整的证明通过；而当提交完全无法枚举时，清单构建会关闭失败，不写出任何清单。然后枚举变更集合并发布清单，生成骨架，为清单中的每个单元写入八个必需的分析字段（多个单元可以共用一段分析，只要该段声明覆盖它们的全部锚点），最后在准确性复核前后分别以 `stage=coverage` 与 `stage=final` 校验。每一轮都重新生成同一个报告；代码返工导致报告过期时走刷新，而不是判为节点失败，且刷新循环有界。解析为不产出报告的工单完全不采集基线。
- **主要边界：** 从不修改代码，也不对变更作出验收结论；强度档位只改变内容厚度，因为三档都必须运行全部机械校验与准确性复核；人类门禁可选且默认关闭；哈希与令牌校验只证明分析与所引用代码绑定，不证明分析正确，而判断含义的准确性复核本身也可能出错；元素层证明元素存在、六段齐全、单元都有绑定，却从不证明元素划分本身正确。

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
- **典型用法：** 检查请求的质量维度，让每个必修 finding 都有证据，并写入已验证 node artifact。对 code/solution review 还检查 under-scope（需求或质量 bar 未满足）、over-scope（无谓改动或超出批准范围）和 scope drift（实现与记录的 scope decision 不一致）。对 `create`，对照原始请求加 accepted capability matrix 检查保真，而不只是 approved solution；没有用户/项目来源的 material exclusion 属于无来源缩窄。存在 reference signature 时，缺失或明显削弱的 signature must capability 是 under-scope；signature should capability 也是 under-scope，除非 accepted matrix 记录了带原因和影响的 deferral；导入无关参考 feature 是 over-scope。
- **主要边界：** 审查对被审对象只读；调用方负责整改和风险决策，原始命令记录不是默认 artifact。范围 finding 是有证据的评审判断，不是机械 scope checker。

## `xc-verification`

[规范契约](../../../../skills/xc-verification/SKILL.md)

- **何时调用：** 实现、诊断、采用或功能基线需要项目定义的验证证据时。
- **用途：** 运行最小充分命令集，把证据映射到验收条件，并记录结果和覆盖缺口。
- **公开入口：** 必填 `workbench_path`、`verification_scope`、`artifact_path`；可选 `inputs`。
- **典型用法：** 读取项目验证政策，先运行局部检查，再按风险扩展回归检查，并记录每条命令及未执行前置条件。对 `create`，把证据映射到 accepted matrix 中的每个 must/should capability；测试全过不等于未验证 capability 已证明。Adaptive regression 或 multi-environment scope 使用独立验证节点；fast pace 不能删除 required scope。
- **主要边界：** 不编造命令或通过标准，不静默弱化验收条件，也不为强行通过而修改产品行为。
