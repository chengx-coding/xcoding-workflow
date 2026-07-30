**语言：** [English (英文)](../../orchestration/authoring.md) | **简体中文 (Simplified Chinese)**

# 受管工作流创作

[`xc-orchestration-author`](../../../skills/xc-orchestration-author/SKILL.md) 把获批工作流设计转换为 runtime 可实例化的受管模板。它负责设计、JSON flow spec、构建和模板验证，不执行节点，也不拥有领域政策。

## 创作流程

支持的流程是：

1. 明确工作流目标、输入、输出、用户决定、失败政策和兼容性约束。
2. 把工作流分解为确定性控制结构和自包含叶子节点。
3. 创建或修改 JSON flow spec。
4. 验证 flow spec。
5. 构建受管 schema version 1 模板。
6. 验证模板。
7. 通过 runtime `init` 和 `next` 执行 smoke test。

公开命令如下：

```powershell
python <author-skill-dir>/scripts/template_builder.py new-spec --out <flow-spec>
python <author-skill-dir>/scripts/template_builder.py validate-spec --spec <flow-spec>
python <author-skill-dir>/scripts/template_builder.py build --spec <flow-spec> --out <template>
python <author-skill-dir>/scripts/template_builder.py validate-template --template <template>
```

详细分解规则见[模板设计方法](../../../skills/xc-orchestration-author/references/template-design-method.md)。

## 设计方法

使用能表达获批行为的最小控制结构：

- `composite mode=sequence` 表示有序阶段。
- `composite mode=parallel` 表示写入范围互不重叠的独立工作。
- `composite mode=switch` 根据预先计算的 blackboard 值确定性路由。
- `composite role=dynamic-group` 表示运行时才发现的子节点集合。
- `gate executor=main` 表示集中的人工决定。
- `loop` 表示有界的轮末评审或修复。

领域含义应放在 `role`、`metadata.*`、instructions、deliverables 和 acceptance 中。不要为评审、撰写、测试、修复、阶段或扩展创建 runtime 节点类型。

大型内容属于 artifact。Blackboard 只应包含影响路由或后续决定的紧凑值。如果条件需要复杂分析，应由 task 完成分析，并写入一个简单结果键供条件或 switch 使用。

## Flow Spec 与 Template ID

JSON flow spec 是确定性 builder 使用的可编辑源。每个节点都有稳定、易读的 kebab-case `template_id`，模板绝不包含 runtime ID。

依赖使用模板本地引用：

```text
depends_on_template="local:prepare"
```

Author 验证本地唯一性和可解析性。Runtime 实例化时把每个本地引用重写为正确的实例专属 runtime ID，并保留来源信息。

Subagent 叶子节点必须提供 `instructions`、`deliverables` 和 `acceptance`。Gate 使用 `executor=main`；composite 和 loop 也使用 `executor=main`。Loop 必须有正数最大轮次和明确的上限结果；switch 必须有 key 和互斥 case/default 子节点。

## 条件、动态工作与循环

条件使用 runtime 刻意限制的表达式集合，默认 `when.policy=reactive`。如果一次性可选分支在共享值变化后仍必须保持 skipped，应使用 `when.policy=latched`。

Dynamic group 应显式表达生命周期：发现工作、添加节点或子树，然后关闭该组。Author 应定义所有权，避免并行 worker 编辑同一产物。

Loop 只在一轮子节点完成后求值 break 和 continue 条件，并且必须有界。不要依赖内部循环控制信号、通用 retry 转换或强制 worker 取消来设计流程；runtime 不提供这些能力。

## 领域包边界

领域 Skill 可以拥有：

```text
assets/
  orchestration-template.xml
references/
  runtime-usage.md
  subagent-contract.md
  artifact-contract.md
  blackboard-contract.md
```

这是职责模式，并不要求创建空文件。该包应说明运行树位置、blackboard 键及允许值、artifact 所有权、单节点 worker prompt 和 gate 行为。

领域包不得复制 runtime 状态机、XML parser、Viewer server 或通用编排脚本。详见[模板包契约](../../../skills/xc-orchestration-author/references/template-package-contract.md)。

## 验证与 Smoke Test

`validate-spec` 在生成前发现格式错误的 flow spec；`build` 确定性创建包含访问和完整性元数据的受管模板；`validate-template` 检查结构规则和 runtime 兼容性。

构建成功仍不足以验收。应通过 runtime 公开命令初始化一次性运行树并调用 `next`，验证首个叶子或并行批次、gate 位置、条件和 dynamic-group 状态符合设计。模板风险较高时，还应覆盖重要分支、循环上限和失败路径。

迁移 prose-oriented Skill 时，应保留领域指导，并用受管模板和公开 runtime driver 替换其过程式 program counter。不要保留旧运行结构的非受管兼容副本。参见[从 prose 工作流迁移](../../../skills/xc-orchestration-author/references/migration-from-skill.md)。

## 创作 Review 清单

发布模板前确认：

- 每个叶子节点都可独立理解，并拥有明确 deliverable。
- 用户 gate 位于证据收集之后、重要操作之前。
- 并行分支不会冲突编辑文件或外部资源。
- 条件是简单、无副作用的路由决定。
- Dynamic group 最终会关闭。
- Loop 有界且定义明确上限结果。
- Failure 和 blocker 有预期恢复路径。
- Runtime 行为保持领域中立。
- `validate-spec`、`build`、`validate-template`、runtime `init` 和 runtime `next` 均通过。
