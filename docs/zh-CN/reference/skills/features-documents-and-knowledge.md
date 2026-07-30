# 功能、文档与知识

[English](../../../reference/skills/features-documents-and-knowledge.md)

这些支撑 Skill 负责持久功能、文档和可选知识边界。

## `xc-feature`

[规范契约](../../../../skills/xc-feature/SKILL.md)

- **何时调用：** new-feature 或 feature-adoption 生命周期已明确选择功能标识时。
- **用途：** 安全创建一个空的受管功能目录，并返回其权威路径。
- **公开入口：** `manage_feature.py init`，必填 `workshop_path` 和 `feature_id`。
- **典型用法：** 初始化目录，再通过文档演进子树创建三份功能基线。
- **主要边界：** 普通工作不得调用；它不创建基线文档，并拒绝路径穿越或已有目录。

## `xc-feature-reconciliation`

[规范契约](../../../../skills/xc-feature-reconciliation/SKILL.md)

- **何时调用：** 普通工作订单引用现有功能，并需在选择变更方案前对账获批意图和当前实现证据时。
- **用途：** 比较代码、可执行测试与功能基线。
- **公开入口：** 必填 `workbench_path`、`feature_id`、`feature_dir`；每个相关功能嵌入一次模板。
- **典型用法：** 在工作订单分析中记录差异，通过文档演进同步符合意图的漂移，并对含糊冲突设置门禁。
- **主要边界：** 不创建功能、不使用锁，也不把代码或文档任何一方视为普遍权威。

## `xc-document`

[规范契约](../../../../skills/xc-document/SKILL.md)

- **何时调用：** 工作流创建、渲染或验证受管 workshop、功能、工作订单或 node-artifact Markdown 文档时。
- **用途：** 强制执行 frontmatter、身份、语言、受众、关联和来源契约。
- **公开入口：** `validate_document.py`，传入 `document_path` 和可选 `expected_kind`；另提供语言验证和确定性模板渲染。
- **典型用法：** 用显式值渲染模板，以已解析语言编写正文，再验证预期的受管文档类型。
- **主要边界：** 不编写正文、不批准文档、不检查不透明 tree reference，也不在 frontmatter 中存放动态任务状态。

## `xc-document-evolution`

[规范契约](../../../../skills/xc-document-evolution/SKILL.md)

- **何时调用：** 受管文档需要持久写作、验证、审查、修订和可选用户批准时。
- **用途：** 为完整文档生命周期提供可复用编排子树。
- **公开入口：** 设置契约定义的 `document.*` blackboard 值并嵌入 `document-evolution-template.xml`。
- **典型用法：** 写作、验证，按配置循环审查和修订，通过可选门禁，最后验证最终文档。
- **主要边界：** 调用方必须串行处理共享 blackboard 键的实例；正文和报告留在 artifact，已封闭树的纠正需要所属门禁和 runtime reopen。

## `xc-knowledge`

[规范契约](../../../../skills/xc-knowledge/SKILL.md)

- **何时调用：** 项目知识 bridge 声明可用来源，或用户明确要求知识库工作时。
- **用途：** 按 bridge 定义的权限咨询、更新或报告可选项目知识源状态。
- **公开入口：** 必填 `workshop_path` 和 `operation`（`consult`、`update` 或 `status`）；可选 `topic`。
- **典型用法：** 读取知识 bridge，使用其中声明的访问规则，并在消费 artifact 中引用检索证据。
- **主要边界：** 不规定提供方或存储布局，不创建默认知识目录，也绝不隐式更新知识。
