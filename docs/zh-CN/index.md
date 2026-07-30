# 文档

**语言：** [English](../index.md) | **简体中文**

这里是 xcoding-workflow 的中文文档。英文文档是规范版本；`docs/zh-CN/` 下的中文树使用对应的页面路径，并完整保持相同主题、事实边界和实质信息。

## 入门

- [安装](getting-started/installation.md)：前置条件、依赖安装、完整替换式安装，以及受管的漂移感知替代方式。
- [快速开始](getting-started/quick-start.md)：创建独立 workshop，并选择第一个受管生命周期。

## 概念

- [架构](concepts/architecture.md)：规范源、生成输出、适配器和所有权边界。
- [Workshop 与 feature](concepts/workshops-features.md)：work order、独立 workshop 历史和显式 feature 基线。

## 工作流

- [选择工作流](workflows/choosing.md)：根据请求结果选择对应生命周期。
- [运行工作流](workflows/running.md)：从设置和证据收集推进到实现、验证与收束。
- [演进工作流](workflows/evolving.md)：通过受管审查修改可移植资产或项目桥接。

## 编排

- [概览](orchestration/overview.md)：编排服务及其公开边界。
- [运行时模型](orchestration/runtime-model.md)：树、节点、调度、状态、artifact 和检查点。
- [模板编写](orchestration/authoring.md)：构建并验证受管模板。
- [查看器](orchestration/viewer.md)：通过只读本地查看器检查运行时树。
- [设计决策与未来方向](orchestration/design-decisions-and-future.md)：当前设计理由，以及明确标记为非规范的可能方向。

## Skill 参考

- [Skill 参考概览](reference/skills/index.md)：发现机制和职责边界。
- [生命周期入口](reference/skills/lifecycle-entry-points.md)
- [调查与决策](reference/skills/investigation-and-decisions.md)
- [Feature、文档与知识](reference/skills/features-documents-and-knowledge.md)
- [实现与质量](reference/skills/implementation-and-quality.md)
- [编排服务](reference/skills/orchestration-services.md)

## 开发

- [文档维护](development/documentation-maintenance.md)：双语结构、证据、链接、检查与审查。

返回[项目中文 README](../../README.zh-CN.md)，或阅读 [MIT License](../../LICENSE)。
