**语言：** [English](../../concepts/workshops-features.md) | **简体中文**

# Workshop、Work Order 与 Feature

## Workshop

每个消费项目都使用固定概念路径 `.xcoding/` 作为受管 workshop。Workshop 属于一个与项目代码仓库相互独立的 Git worktree。这样既能让工作流文档、运行时 checkpoint 和节点 artifact 不进入产品 commit，又能保留它们自身的持久历史。

Workshop 的桥接文档记录项目策略。`WORKFLOW.md` 描述项目身份、命令、约定和约束；`KNOWLEDGE.md` 说明项目知识源是否存在以及如何使用。它们都不能替代通用的规范 `xc-*` Skill。

## Work Order 与 Workbench

Work order 是一次调查、变更、修复、评审或维护工作的持久单元。[work order 打开器](../../../skills/xc-open-work-order/SKILL.md)会创建避免冲突的 ID 并返回权威 workbench 路径，但不会创建文档、运行时树、feature 目录或 commit。

标准 workbench 的概念结构如下：

```text
.xcoding/work-orders/<work-order-id>/
  goal.md
  analysis.md       # 需要证据或方案比较时
  solution.md       # 需要选择变更策略时
  result.md
  runtime/
  artifacts/
```

`goal.md`、`analysis.md`、`solution.md` 和 `result.md` 持久保存目标、证据、决策和结果。动态状态、执行顺序、重试状态、循环状态和 blocker 属于受管运行时树；worker 的详细证据应写入 `artifacts/`，而不是运行时 blackboard。

一个 work order 可以关联零个、一个或多个已有 feature。通用的 [work 生命周期](../../../skills/xc-work/SKILL.md)不会仅因为一项变更需要持久管理就自动创建 feature。

## Feature 基线

一个受管 feature 拥有稳定标识和三份已批准的基线文档：

```text
.xcoding/features/<feature-id>/
  contract.md
  solution.md
  verification.md
```

- `contract.md` 定义可观察需求、边界、兼容性和失败语义。
- `solution.md` 记录已批准的技术设计与实现不变量。
- `verification.md` 把需求映射到用于证明需求的验证证据。

Feature 基线不是任务清单或状态台账。基线修订按需经过受管文档演进、评审和 gate。

## 当前证据与已批准意图

XC 明确区分两类事实：

| 来源 | 能够证明的内容 |
| --- | --- |
| 项目代码与可执行测试 | 当前实现行为的证据 |
| 已批准的 feature 基线 | 产品目标意图 |

两者都不是无条件的唯一权威。[feature 协调契约](../../../skills/xc-feature-reconciliation/SKILL.md)会在普通的 feature 相关 work order 选择方案前比较两者。若有证据支持且不改变产品意图，可以通过独立的文档演进路径同步基线；含糊冲突、产品意图变化或并发基线修改则必须进入用户 gate。

## 何时可以创建 Feature

Feature 创建必须始终是显式行为：

- [新 feature](../../../skills/xc-new-feature/SKILL.md)为尚无受管身份的行为创建 feature，并在实现前批准其基线。
- [Feature 采用](../../../skills/xc-feature-adoption/SKILL.md)依据代码和测试证据，为已有但未受管的行为建立基线。采用过程不会静默改变或修复产品。
- [Feature 目录服务](../../../skills/xc-feature/SKILL.md)只能受上述两个工作流调用来初始化目录。
- 普通 work order 可以引用已有 feature ID，但不能创建或采用 feature。

这项规则避免某个实现细节或临时维护请求在没有显式生命周期和批准决定的情况下变成持久产品契约。
