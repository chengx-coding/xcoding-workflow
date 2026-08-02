# xcoding-workflow

**语言：** [English](README.md) | **简体中文**

xcoding-workflow 是一套可移植、由 Skill 驱动的 Agent 编码工作流的规范源。它覆盖发现、设计、实现、诊断、验证、审查、修复和交付，且不绑定特定编程语言、框架或 Agent 宿主。

## 核心模型

- 规范的 `xc-*` Skill 包定义公开工作流入口和可复用服务。
- 每个消费项目都通过固定的 `.xcoding` 路径提供 workshop，其背后必须是与项目源码仓库相互独立的 Git 工作树。
- 持久工作以 work order 运行。运行时编排负责调度和状态；简短的 blackboard 值用于协调决策，文档和其他大段证据则保存在 artifact 中。
- Managed feature 必须显式创建。新功能使用 new-feature 工作流，现有代码纳管使用 adoption 工作流，可能关联零个、一个或多个已有 feature 的变更使用普通 work 工作流。

## 选择直接或受管工作

XC 根据六个已确认事实选择治理方式：`needs_persistence`、`material_impact`、`difficult_rollback`、`crosses_sessions`、`multiple_actors` 和 `audit_required`。每项事实只能为 `no`、`yes` 或 `unknown`。只有六项均已确认为 `no` 时，工作才能保持 direct；任一 `yes`、任一 `unknown` 或分类不可用都会进入受管的 [`xc-work`](skills/xc-work/SKILL.md) 生命周期。显式调用 `xc-work operation=run` 始终是受管执行。

公开的 fail-closed 分类边界通过可执行命令 `python skills/xc-work/scripts/classify.py [事实参数]` 提供。它会把省略事实补为 `unknown`，并在输入、执行、超时或输出校验失败时始终返回成功的 managed 升级；严格低层分类器仅用于诊断。该边界会验证可观察的进程结果，但不认证调用方、解释器、可执行文件字节或宿主。确认事实前应读取适用项目政策，项目 bridge 只能收紧事实。Direct 工作出现新证据时，必须在下一项实质操作前重新分类；结果不再是全 `no` 时，通过 `xc-work operation=run` 升级。

更强的模型可以在主会话中完成更多推理，也可以在 direct 路径上避免不必要的拆分。模型名称、供应商、上下文窗口和项目技术栈不能改变事实，也不能成为绕过受管 gate、artifact、限定范围的 control packet 或验证的理由。

## 前置条件

- Git；如果启用了 workshop 检查点提交，还需要配置 Git 身份。
- Python 和 `pip`，用于运行仓库脚本并安装[声明的依赖](requirements.txt)。
- 能够发现并调用已安装 Skill 包的 Agent 宿主。

项目目前尚未发布正式的 Python 版本或 Agent 宿主兼容矩阵。请使用实际环境中的 Python 运行时和宿主验证工作流。

## 安装 Skills

在本仓库的检出目录中安装 Python 依赖：

```console
python -m pip install -r requirements.txt
```

创建消费端宿主的目标 skills 目录，然后运行根安装器：

```console
python install_skills.py --target-skills /absolute/path/to/consumer/.agents/skills
```

**该命令会完整替换目标中的全部 `xc-*` 包。** 它会删除目标 skills 目录下名称以 `xc-` 开头的每个目录，移除原有 XC 安装清单，再从当前检出安装完整包。目标 `xc-*` 包中的本地修改不会保留。名称不以 `xc-` 开头的包不会被改动。

如果受管更新必须在替换前检测漂移，请使用由 [`xc-workflow-evolution`](skills/xc-workflow-evolution/SKILL.md) 拥有的安装器：

```console
python skills/xc-workflow-evolution/scripts/install_xc_skills.py --source-root /absolute/path/to/xcoding-workflow --target-root /absolute/path/to/consumer/.agents --manifest /absolute/path/to/consumer/.agents/.xc-skill-install-manifest.json
python skills/xc-workflow-evolution/scripts/install_xc_skills.py --source-root /absolute/path/to/xcoding-workflow --target-root /absolute/path/to/consumer/.agents --manifest /absolute/path/to/consumer/.agents/.xc-skill-install-manifest.json --check
```

受管安装器复制完整包，保留非 `xc-*` 包，记录源版本和文件哈希，并在目标 `xc-*` 内容发生变更、缺失或出现意外内容时拒绝继续。首次受管安装要求目标中不存在未纳管的 `xc-*` 包；由根安装器建立的安装已经包含所需清单。

## 创建 workshop

仅当消费项目根目录中还不存在 `.xcoding` 时，才从该目录运行以下命令。命令会在项目旁创建独立 workshop 仓库，并将其中的 workshop 目录暴露到项目的固定路径。

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

在识别并保全现有 `.xcoding` 所指向的 workshop 之前，不要替换该路径。

## 开始受管工作

首先使用消费项目根目录及其 `.xcoding` workshop 调用 [`xc-workshop-setup`](skills/xc-workshop-setup/SKILL.md)。它会建立项目专用的工作流桥接和知识指引，不会虚构项目命令或约定。

然后调用一个生命周期入口：

- [`xc-work`](skills/xc-work/SKILL.md)：用于调查、迭代、修复、审查、维护或跨 feature 工作。
- [`xc-new-feature`](skills/xc-new-feature/SKILL.md)：用于创建新的显式 managed feature 及其已批准基线。
- [`xc-feature-adoption`](skills/xc-feature-adoption/SKILL.md)：用于在后续变更前，为现有未纳管 feature 推导受管基线。

不同 Agent 宿主的调用语法可能不同。请传入所选 Skill 公开契约中记录的参数，包括 `workshop_path` 和 `project_root`。

## 文档

- [文档索引](docs/zh-CN/index.md)
- [安装](docs/zh-CN/getting-started/installation.md)
- [快速开始](docs/zh-CN/getting-started/quick-start.md)

消费端安装与 `build_agents.py` 相互独立。该开发辅助脚本把本仓库规范的 `skills/` 树镜像到当前检出使用的本地 Agent 发现目录；它不是消费端安装器。

## 许可证

本项目采用 [MIT License](LICENSE)。
