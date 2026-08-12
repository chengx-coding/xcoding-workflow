# xcoding-workflow

**语言：** [English](README.md) | **简体中文**

xcoding-workflow 帮助编码 Agent 把一个需求推进到经过测试和审查的结果。它不绑定特定编程语言、框架或运行编码 Agent 的应用；本文把这类应用称为 **Agent 宿主**。

## 它能做什么

- XC 由必要的 `xcoding` CLI package 和一组称为 **Skills** 的工作流模块组成。
- 小型、低风险的任务可以直接完成。
- 需要计划、审查、故障恢复或长期留痕的任务使用**受管工单**。工单把目标、决策、进度和证据保存在一起。
- 显式选择自适应受管工单时，可以从一个合并工作叶子节点和一个 finalizer 开始，再根据已确认事实增加文档、分析、门禁、验证、审查与恢复。
- 项目中的 `.xcoding` 目录是工作流专用空间。它使用独立的 Git 工作树，也就是专门保存工作流历史的独立工作目录，避免把这些记录混入源码提交历史。
- 只有在你明确创建或接管时，长期维护的产品功能才会成为受管功能。普通维护不会自动创建功能。

## 选择直接或受管工作

开始修改前，XC 会先判断任务是否适合一次性直接完成。它会检查六个问题：

1. 是否必须把进度或证据保留到以后？
2. 是否可能影响共享代码、公开约定、数据、权限、安全边界、基础设施或发布内容？
3. 是否无法通过一个步骤完整回退？
4. 是否必须等待、重启或在另一个会话中继续？
5. 是否需要多个人、Agent 或外部系统协作？
6. 是否必须保留审查、批准、验证或审计记录？

每个答案只能是 `yes`、`no` 或 `unknown`。

- 只有六个答案都明确为 `no` 时，才使用**直接执行**。
- 只要有一个答案是 `yes`、`unknown` 或无法确认，就使用**受管工单**。

即使通用规则允许直接执行，项目自己的规则仍可要求使用受管工单。如果直接执行过程中出现新信息，应先重新回答这六个问题，再继续修改。

### 自动化调用

公开分类命令是：

```console
python skills/xc-work/scripts/classify.py [事实参数]
```

六个参数分别是 `needs_persistence`、`material_impact`、`difficult_rollback`、`crosses_sessions`、`multiple_actors` 和 `audit_required`。省略的参数会按 `unknown` 处理。输入错误、超时、执行失败或无效输出都会得到受管结果，不会静默放行直接执行。

需要启动受管工单时，调用 [`xc-work`](skills/xc-work/SKILL.md) 并使用 `operation=run`。这个操作始终是受管执行。模型名称、供应商、上下文窗口大小和项目技术栈都不能改变六个答案，也不能取消必要的审查和验证。

`operation=adaptive-run` 是显式选择的受管替代路径。它保留持久 runtime，但允许最小 workbench 不创建强制顶层文档。`operation=plan` 根据治理、项目政策、范围、清晰度、风险、验证、协作、持续时间、审计和 `adaptive|fast|thorough` 节奏事实单调增加 capability。省略 operation 或显式 `run` 仍保持原完整生命周期。

## 前置条件

- Git。如果希望 XC 自动保存工作流检查点，还需要配置 Git 身份。
- CPython 3.12 或更高版本。`0.1.0` 的正式验证基线是 Windows x86_64 + CPython 3.12.13；除非 release 证据另有说明，其他可接受版本不属于正式基线。
- 用于隔离工具安装的 `uv`。
- Windows x86_64 上的 Codex、OpenCode、Claude Code 或 Trae。精确验证的宿主版本和实验性环境见[安装](docs/zh-CN/getting-started/installation.md)。

## 安装 XC

受支持的 distribution 是 `xcoding-workflow`；`0.1.0` 只通过不可变 GitHub Release 分发，不发布到 PyPI。如果不可变 release 及其完整性文件尚不可用，就还没有受支持的公开安装产物。

从同一个 release 下载 wheel 和完整性文件，按[安装](docs/zh-CN/getting-started/installation.md)中的说明完成校验，再安装本地 wheel：

```console
uv tool install /absolute/path/to/xcoding_workflow-0.1.0-py3-none-any.whl
xcoding version --json
```

安装结果只提供 `xcoding` 命令。在消费项目根目录为一个或多个显式宿主执行设置；重复的 `--host` 值共同构成完整 desired host set：

```console
xcoding setup --project-root /absolute/path/to/consumer --host codex --host trae
```

追加 `--dry-run` 可以在零写入情况下检查同一计划。Setup 报告中断 journal 时，应显式恢复；需要还原上一份成功 generation 时，执行 rollback：

```console
xcoding setup --project-root /absolute/path/to/consumer --recover
xcoding setup --project-root /absolute/path/to/consumer --rollback
```

Setup 会拒绝未纳管冲突和已漂移的受管文件，不会覆盖它们。XC 不提供 `install.ps1`、`install.sh`、远程脚本 pipe 命令、自动宿主检测或 force 选项。宿主路径、desired-state 更新、恢复、回滚、release 完整性和支持政策详见[安装](docs/zh-CN/getting-started/installation.md)。

## 创建工作流空间

XC 把计划、进度、决策和证据保存在 `.xcoding` 中。这个目录应使用独立的 Git 仓库，避免把工作流历史混入源码提交历史。

仅当项目根目录中还不存在 `.xcoding` 时，才从该目录运行以下任一示例。命令会在项目旁创建独立仓库，并把其中的 `.xcoding` 目录连接到项目。

POSIX shell：

```sh
PROJECT_ROOT="$(pwd)"
WORKSHOP_ROOT="$(dirname "$PROJECT_ROOT")/$(basename "$PROJECT_ROOT")-xc-workshop"
mkdir -p "$WORKSHOP_ROOT/.xcoding"
git -C "$WORKSHOP_ROOT" init
ln -s "$WORKSHOP_ROOT/.xcoding" "$PROJECT_ROOT/.xcoding"
```

Windows PowerShell：

```powershell
$ProjectRoot = (Get-Location).Path
$WorkshopRoot = Join-Path (Split-Path $ProjectRoot -Parent) "$(Split-Path $ProjectRoot -Leaf)-xc-workshop"
New-Item -ItemType Directory -Force (Join-Path $WorkshopRoot ".xcoding") | Out-Null
git -C $WorkshopRoot init
New-Item -ItemType Junction -Path (Join-Path $ProjectRoot ".xcoding") -Target (Join-Path $WorkshopRoot ".xcoding") | Out-Null
```

如果 `.xcoding` 已经存在，应先确认它指向哪里并保留现有工作流空间，不要直接替换。

## 启动第一个受管任务

先运行一次 [`xc-workshop-setup`](skills/xc-workshop-setup/SKILL.md)，传入项目根目录和 `.xcoding` 路径。它会记录项目真实使用的构建、测试、文档和提交规则。

然后选择一个入口：

- [`xc-work`](skills/xc-work/SKILL.md)：用于普通调查、修复、审查或维护。
- [`xc-new-feature`](skills/xc-new-feature/SKILL.md)：用于启动一个需要由 XC 长期管理的新产品功能。
- [`xc-feature-adoption`](skills/xc-feature-adoption/SKILL.md)：用于在后续修改前，把现有功能纳入 XC 管理。

不同 Agent 宿主的调用语法可能不同。请使用宿主通常的 Skill 调用方式，并传入所选入口记录的 `project_root` 和 `workshop_path` 参数。

## 文档

- [文档索引](docs/zh-CN/index.md)
- [安装](docs/zh-CN/getting-started/installation.md)
- [快速开始](docs/zh-CN/getting-started/quick-start.md)

`build_agents.py` 只用于开发本仓库。它刷新当前检出中的本地 Skill 镜像，不会把 XC 安装到其他项目。

## 许可证

本项目采用 [MIT License](LICENSE)。
