# 编排服务

[English](../../../reference/skills/orchestration-services.md)

这些服务设计、运行和可视化受管编排，但不接管领域工作。

## `xc-orchestration-author`

[规范契约](../../../../skills/xc-orchestration-author/SKILL.md)

- **何时调用：** 获批工作流需要新的受管模板，或需要把 prose 流程转为 runtime 控制时。
- **用途：** 设计并验证 JSON flow specification，构建带完整性保护的 schema-version-1 模板。
- **公开入口：** `template_builder.py` 的 `new-spec`、`validate-spec`、`build`、`validate-template` 命令。
- **典型用法：** 建模阶段、依赖、门禁、动态组和有界循环；构建模板并 smoke-test `init -> next`。
- **主要边界：** 不执行运行时节点；领域数据应使用 metadata 和 artifact，不得新增运行时节点类型或把大段内容放入 blackboard。

## `xc-orchestration-runtime`

[规范契约](../../../../skills/xc-orchestration-runtime/SKILL.md)

- **何时调用：** 工作流需要调度、节点转换、受控状态更新、嵌入子树、完整性操作、快照或持久化时。
- **用途：** 为受管运行时树和事务性 workshop checkpoint 提供领域中立控制面。
- **公开入口：** `orchestration.py` 的 `init`、`next`、`start`、`complete`、`fail`、`block` 等生命周期命令，以及已记录的查询和恢复命令。
- **典型用法：** 从模板初始化，请求 ready work，仅启动可执行叶节点，并用简洁证据和声明 artifact 终止 running 节点。
- **主要边界：** 绝不直接读取或编辑受管 XML；worker 只执行一个节点，完整性无效时需显式修复，成功树在获批 reopen 前保持 sealed。

## `xc-orchestration-viewer`

[规范契约](../../../../skills/xc-orchestration-viewer/SKILL.md)

- **何时调用：** 用户要求打开、监控或可视化受管运行时进度时。
- **用途：** 为 runtime 所有的仅回环、只读 viewer 提供无脚本 facade。
- **公开入口：** 用 `--tree` 启动 runtime 的 `viewer_server.py`；非 sibling 安装使用 `runtime_skill_dir`，仅为额外许可目录使用 `--allow-root`。
- **典型用法：** 启动 detached 本地服务，在浏览器查看 snapshot，平移或缩放图，并下载完整 SVG。
- **主要边界：** 不拥有 parser、状态机、server 或 frontend，也不暴露修改 endpoint；选定树和 native picker 授权保持最小范围。
