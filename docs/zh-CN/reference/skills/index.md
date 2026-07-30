# Skill 参考

[English](../../../reference/skills/index.md)

XC 工作流提供两类 Skill：

- **入口 Skill** 用于启动或选择生命周期，适合首次采用工作流、开启持久工作、创建或采用功能，以及演进工作流资产。
- **支撑 Skill** 在生命周期内提供调查、文档、实现、质量、功能、知识或编排能力。除非其契约明确提供独立操作，否则应通过拥有工作订单的生命周期调用。

每个 Skill 的规范契约仍是 Git 已跟踪的 `SKILL.md`。这些页面只概述发现和用法，不替代规范契约。

## 目录

- [生命周期入口](lifecycle-entry-points.md)
- [调查与决策](investigation-and-decisions.md)
- [功能、文档与知识](features-documents-and-knowledge.md)
- [实现与质量](implementation-and-quality.md)
- [编排服务](orchestration-services.md)

应选择能完整覆盖请求的最小 Skill 集合，完整阅读每个所选契约，并遵守生命周期门禁和运行时所有权边界。
