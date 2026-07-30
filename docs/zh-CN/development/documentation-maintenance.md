# 文档维护

**语言：** [English (英文)](../../development/documentation-maintenance.md) | **简体中文 (Simplified Chinese)**

## 语言契约

英文 README 和文档页面是规范版本。`docs/` 下每个英文页面都必须在 `docs/zh-CN/` 下具有相同相对路径的简体中文镜像。镜像必须保持相同主题、事实边界、导航和实质信息，但无需逐行直译。

每个页面都使用显著的语言选择器，列出全部已支持语言：

```markdown
**语言：** [English (英文)](<canonical-path>) | **简体中文 (Simplified Chinese)**
```

中文镜像页应把简体中文显示为当前语言，并链接 English。不要只留下读者可能不认识的母语名称。

新增、移动、重命名或删除页面时，必须在同一变更中处理两种语言，并同时更新受影响的导航、链接、锚点和文档 checker 的获批拓扑。不得用临时空镜像满足结构检查。

## 证据政策

只有 Git 已跟踪的规范契约、源代码、配置和测试支持的内容才能描述为当前行为。每次编辑都要依据这些来源复核命令、默认值、路径、状态语义、失败行为和所有权边界。历史材料或本地笔记不能作为公开主张的证据。

未实现想法只能出现在编排设计页面中明确标注的“非规范未来方向”部分。它们不得承诺交付，不得给出排期或路线图承诺，也不得提供兼容保证。

## 公开链接

公开页面只能链接到大小写精确、在干净 checkout 中存在、已跟踪或将在同一发布中 staged，且未被 ignore 或 exclude 的目标。不得链接本地维护资产、workshop 状态、私有指令、生成的本地 adapter 或其他仅存在于当前 checkout 的上下文。两种语言中的相对链接和锚点都必须可解析。

## 审查证据

机械检查不能证明双语语义等价。独立语义审查必须记录：

- reviewer 职责和实际 reviewer identity；
- 被审 revision 或可复现的完整 diff identity；
- 每个文档页面对和根 README 对的 accepted 或 rejected outcome、事实结论与 finding 引用；
- Skill 覆盖、当前与未来措辞、安装说明、兼容性缺口和隐藏路径泄漏等横切检查；
- 每个 rejected 或 stale outcome 的整改责任和新审查结果；
- 最终 accepted 或 rejected 结论；声称接受时不得仍有 unresolved、rejected 或 stale 页面对。

审查后发生任何内容变化，受影响 outcome 即为 stale，必须重新审查。

## 验证

并行编写页面时，对本节点拥有的页面对、语言切换、本地链接与锚点、精确大小写、相关 Skill 名称和事实一致性运行局部检查。不得通过创建 sibling 所有的占位页面来强行让完整 checker 通过。

所有页面集成后：

1. 运行文档 checker 单元测试。
2. 对完整仓库运行 checker。
3. 发布或 commit 前运行 strict tracked 模式。
4. 完成独立双语语义审查。
5. 运行仓库完整测试套件、适用的生成输出检查和 `git diff --check`。

在所属工作订单 artifact 中记录命令、结果、跳过的检查和残余风险。checker 失败、审查 stale 或存在未解决语义 finding 时必须阻止接受。
