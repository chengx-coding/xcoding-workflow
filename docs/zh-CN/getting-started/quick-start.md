# 快速开始

**语言：** [English](../../getting-started/quick-start.md) | **简体中文**

本指南从消费项目开始，并假设 `PATH` 中已有必要的 `xcoding` 工具，且至少一个 Agent 宿主已经由 `xcoding setup` 配置。如果任一前提缺失，请先阅读[安装](installation.md)。安装 wheel 会提供工具；setup 会在显式项目根目录中安装并拥有所选宿主的 XC Skills 与 subagent 定义。`build_agents.py` 只用于 xcoding-workflow 检出目录的开发镜像。

## 1. 选择消费项目

在消费项目的 Git 根目录打开终端：

```console
cd /absolute/path/to/project
git rev-parse --show-toplevel
```

后续路径示例均假定当前目录是项目根目录。

## 2. 选择 workshop 拓扑

[`xc-workshop-setup`](../../../skills/xc-workshop-setup/SKILL.md) 会询问一次固定路径 `.xcoding` 与业务仓库的关系，然后把答案记录为 `.xcoding/xc-orchestration-runtime.json` 中的 `workshop.topology`。它会推荐默认值 `independent-link`，该值保持当前已文档化的行为。脚本或非交互场景中可传入固定的 `workshop_topology` 参数以跳过提问。

四种拓扑是：

- `independent-link`（默认）：workshop 历史保存在项目外的一个独立 Git 仓库中，并通过目录链接接入项目 `.xcoding`。产品的 `.gitignore` 会忽略 `.xcoding` 链接目标。
- `independent-nested`：workshop 历史保存在项目内 `.xcoding` 的独立 Git 仓库中。产品的 `.gitignore` 会忽略 `.xcoding`。
- `same-repo`：`.xcoding` 是直接版本化在产品仓库中的一个普通目录，不写入任何 `.gitignore` 条目。由于引擎的 checkpoint commit 会进入产品历史，且 work order 状态会跟随产品分支，该拓扑要求在运行时配置中显式声明 `git.auto_commit`。
- `no-git`：`.xcoding` 是不带任何 Git 仓库的普通未跟踪目录，不写入 `.gitignore` 条目，也没有 checkpoint 历史。

仅当项目中没有既有 `.xcoding` 路径时，才运行下面与所选拓扑匹配的创建序列。如果该路径已存在，请先检查它的解析位置并保留对应 workshop，不要替换。对于 `independent-link` 与 `independent-nested`，setup 还会在产品 `.gitignore` 中追加根锚定的 `/.xcoding/` 条目；`same-repo` 与 `no-git` 不写入任何内容。

`independent-link`（项目外独立仓库外加目录链接）：

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

`independent-nested`（在 `<project>/.xcoding` 内 `git init`）：

POSIX shell：

```sh
mkdir -p "$(pwd)/.xcoding"
git -C "$(pwd)/.xcoding" init
```

Windows PowerShell：

```powershell
$ProjectRoot = (Get-Location).Path
New-Item -ItemType Directory -Force (Join-Path $ProjectRoot ".xcoding") | Out-Null
git -C (Join-Path $ProjectRoot ".xcoding") init
```

`same-repo`（版本化在产品仓库中的普通目录）：

POSIX shell：

```sh
mkdir -p "$(pwd)/.xcoding"
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force (Join-Path (Get-Location).Path ".xcoding") | Out-Null
```

`no-git`（普通未跟踪目录）：

POSIX shell：

```sh
mkdir -p "$(pwd)/.xcoding"
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force (Join-Path (Get-Location).Path ".xcoding") | Out-Null
```

对于两种独立拓扑，请确认 Git 报告两个不同的顶层路径：

```console
git -C . rev-parse --show-toplevel
git -C .xcoding rev-parse --show-toplevel
```

如果没有合适的全局 Git 身份，请在使用自动检查点提交前为 workshop 仓库配置身份。

## 3. 初始化项目工作流指引

请 Agent 宿主使用以下参数调用 [`xc-workshop-setup`](../../../skills/xc-workshop-setup/SKILL.md)：

```text
workshop_path: /absolute/path/to/project/.xcoding
project_root: /absolute/path/to/project
```

设置工作流会打开自己的持久 work order，并建立项目专用的工作流桥接和知识指引。收到询问时，请提供真实的项目命令、语言选择、仓库边界和约束。对于未知的项目事实，工作流必须保留为未解决状态，不能自行虚构。

完成设置后，再启动普通工作或管理 feature。

## 4. 选择第一个生命周期

### 现有项目工作

调查、代码变更、修复、审查或维护使用 [`xc-work`](../../../skills/xc-work/SKILL.md)。它可以关联零个、一个或多个已经纳管的 feature，且绝不会隐式创建 feature。

```text
Invoke xc-work with:
workshop_path: /absolute/path/to/project/.xcoding
project_root: /absolute/path/to/project
request: <目标结果和约束>
mode: change
feature_ids: []
```

根据请求选择 `investigation`、`change`、`repair`、`review` 或 `maintenance` 模式。

### 全新的 managed feature

当请求行为需要新的显式 feature 和已批准 feature 基线时，使用 [`xc-new-feature`](../../../skills/xc-new-feature/SKILL.md)。

```text
Invoke xc-new-feature with:
workshop_path: /absolute/path/to/project/.xcoding
project_root: /absolute/path/to/project
feature_id: <稳定的小写 slug>
request: <feature 目标、边界和约束>
```

这是创建新 managed feature 目录的常规生命周期。不要只为普通维护添加标签而使用它。

### 纳管现有未管理 feature

当代码已经实现某项 feature，但尚无 managed baseline 时，使用 [`xc-feature-adoption`](../../../skills/xc-feature-adoption/SKILL.md)。

```text
Invoke xc-feature-adoption with:
workshop_path: /absolute/path/to/project/.xcoding
project_root: /absolute/path/to/project
feature_id: <稳定的小写 slug>
code_entry: <现有模块、接口或路径集合>
request: <纳管动机和已知约束>
```

Adoption 会推导有证据支持的基线，不会静默修改或修复产品。后续产品变更应通过单独的 `xc-work` 请求。

## 5. 让受管生命周期控制状态

在显式用户门禁中提供决策，并让运行时公开接口负责节点调度、转换和检查点。代码和项目提交保留在项目仓库；work order 文档、feature 基线、运行时状态和节点 artifact 保留在 workshop 历史中，它在默认 `independent-link` 拓扑下独立于项目仓库。

继续查看[文档索引](../../index.md)，了解概念、工作流指引、编排细节和完整 Skill 参考。
