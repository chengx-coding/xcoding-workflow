# 编排服务

**语言：** [English](../../../reference/skills/orchestration-services.md) | **简体中文**

这些服务设计、运行和可视化受管编排，但不接管领域工作。

## `xc-orchestration-author`

[规范契约](../../../../skills/xc-orchestration-author/SKILL.md)

- **何时调用：** 获批工作流需要新的受管模板，或需要把 prose 流程转为 runtime 控制时。
- **用途：** 设计并验证 JSON flow specification，构建带完整性保护的 schema-version-1 模板。
- **公开入口：** `template_builder.py` 的 `new-spec`、`validate-spec`、`build`、`validate-template` 命令。
- **典型用法：** 建模阶段、依赖、gate、dynamic group、有界循环和叶子节点自有 control metadata；验证 flow spec，构建生成模板，验证模板并 smoke-test `init -> next`。
- **主要边界：** JSON flow spec 是可编辑源，生成的 XML 不得手工修改。Author 不执行运行时节点；领域数据应使用 metadata 和 artifact，不得新增运行时节点类型或把大段内容放入 blackboard。

## `xc-orchestration-runtime`

[规范契约](../../../../skills/xc-orchestration-runtime/SKILL.md)

- **何时调用：** 工作流需要调度、节点转换、受控状态更新、嵌入子树、完整性操作、快照或持久化时。
- **用途：** 为受管运行时树和事务性 workshop checkpoint 提供领域中立控制面。
- **可移植公开入口：** `orchestration.py` 的 `init`、`next`、`control-packet`、`start`、`complete`、`fail`、`block` 等生命周期命令，以及 `unblock`、`retry-failed`、`reopen` 等已记录的查询和恢复命令。Opt-in completion 增加可重复的 `--check-result-json`；opt-in gate 增加 `--gate-outcome` 和 `--decision`。
- **Prerelease package adapter：** 匹配的仓库 package 以 `xc runtime <command> ...` 暴露同一组 23 个命令。它直接执行 application，不是 daemon transport，也不是已发布的消费端入口。
- **典型用法：** 从模板初始化，请求 ready work，读取所选叶子节点的 scoped packet，仅启动该可执行叶子，并用简洁证据和声明 artifact 终止它。失败后需要再次执行同一个已批准叶子契约时，`retry-failed --reason` 会归档该 attempt 并恢复普通调度。
- **主要边界：** 绝不直接读取或编辑受管 XML；worker 只执行一个节点，来源投影不是 start 权限，完整性无效时需显式修复，成功树在获批 reopen 前保持 sealed。

### Runtime 实现所有权

`src/xcoding/runtime/` 是 runtime core、Runtime Application Service 和完整命令
规范的可编辑源。Package CLI 与 legacy Skill adapter 都调用该 application
service；两者都不拥有事务逻辑。

完整 runtime Skill 仍可独立安装。它的 `scripts/_runtime_compat/` 是规范模块的
确定性生成副本，`runtime_core.py` 与 `orchestration.py` 是兼容 alias 或
adapter。Generation 检查会拒绝漂移，Bundle 检查会要求完整载荷；消费端不得把
该载荷作为第二份实现进行编辑。

### 控制契约

`metadata.control_packet.*` 声明仅属于叶子节点的来源类别、阈值和选定 blackboard 标量。缺少声明时返回 `control_packet_not_declared`；selector 无法解析、来源未终止、来源或 artifact 数量不足，或选定键缺失时，返回 `control_packet_unavailable`，且不返回残缺 packet。

`metadata.completion.*` 可以要求 `summary`、`validation`、artifact 数量与路径，以及归一化 check receipt。Receipt 畸形、过大、重复或未声明时返回 `invalid_check_result`；字段、artifact、必需 check、subject 或 fact 不满足时返回 `completion_requirements_failed`。Receipt 是不可信的未签名自报告。Runtime 会比较形状和声明值，但不会运行 validator、绑定 claimant 或证明执行；完全匹配的伪造值会被接受。

`metadata.gate.*` 声明允许的结构化 outcome、是否要求 decision，以及可选 outcome key。完成操作可能返回 `gate_outcome_required`、`invalid_gate_outcome`、`gate_decision_required`、`gate_outcome_conflict` 或 `gate_outcome_not_allowed`。Outcome 与其声明的 blackboard key 原子写入，但 runtime 不认证 CLI 调用者。

在 author 验证、runtime 验证与初始化以及动态 `add-node` 时，这三个已识别前缀都会针对未知键、非法 owner、畸形值或不完整声明 fail closed，并返回 `invalid_control_metadata`。这些扩展是 `schema_version=1` 内的 opt-in 能力：不带新 metadata 的现有 schema-version-1 节点保留 legacy 命令与结果行为；更早 schema 格式仍不受支持。

Runtime 不提供 trusted execution、claim binding、typed blackboard、宿主工具 mediation 或模型专用 profile，也不能阻止 `start` 前使用普通宿主工具；这些仍由宿主和调用方负责。

`retry-failed` 是显式 attempt 恢复，不是自动 retry 政策。它只接受失败的 task 或 gate 叶子，把原结果和 artifact 保存为有序历史，支持 `--expected-revision`，并且不会重置 succeeded 或 running 的同级工作。节点查询和 snapshot 会暴露历史；retry-aware artifact 条目包含 attempt 编号。引擎生成的 switch 和 loop 失败不适用该操作。

## `xc-orchestration-viewer`

[规范契约](../../../../skills/xc-orchestration-viewer/SKILL.md)

- **何时调用：** 用户要求打开、监控或可视化受管运行时进度时。
- **用途：** 为 runtime 所有的仅回环、只读 viewer 提供无脚本 facade。
- **公开入口：** 用 `--tree` 启动 runtime 的 `viewer_server.py`；非 sibling 安装使用 `runtime_skill_dir`，仅为额外许可目录使用 `--allow-root`。
- **典型用法：** 启动 detached 本地服务，在浏览器查看 snapshot，平移或缩放图，并下载完整 SVG。
- **主要边界：** 不拥有 parser、状态机、server 或 frontend，也不暴露修改 endpoint；选定树和 native picker 授权保持最小范围。
