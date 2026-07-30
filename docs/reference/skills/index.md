# Skill Reference

**Language:** **English** | [简体中文](../../zh-CN/reference/skills/index.md)

The XC workflow exposes two kinds of Skills:

- **Entry Skills** start or select a lifecycle. Use them when adopting the workflow, opening durable work, creating or adopting a feature, or evolving workflow assets.
- **Supporting Skills** provide investigation, document, implementation, quality, feature, knowledge, or orchestration capabilities inside a lifecycle. Call them through the lifecycle that owns the work order unless their contract explicitly provides a standalone operation.

The canonical contract for each Skill remains its tracked `SKILL.md`. These pages summarize discovery and usage; they do not replace those contracts.

## Catalog

- [Lifecycle entry points](lifecycle-entry-points.md)
- [Investigation and decisions](investigation-and-decisions.md)
- [Features, documents, and knowledge](features-documents-and-knowledge.md)
- [Implementation and quality](implementation-and-quality.md)
- [Orchestration services](orchestration-services.md)

Choose the smallest set of Skills that covers the request, read every selected contract completely, and respect the lifecycle's gates and runtime ownership boundaries.
