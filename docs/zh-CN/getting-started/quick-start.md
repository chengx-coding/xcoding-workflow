# 快速开始

[English](../../getting-started/quick-start.md)

本指南从消费项目开始，并假设其 Agent 宿主已经能够发现安装好的 `xc-*` Skill 包。如果尚未安装，请先阅读[安装](installation.md)。消费端安装使用 `install_skills.py` 或受管安装器；`build_agents.py` 只用于 xcoding-workflow 检出目录的开发镜像。

## 1. 选择消费项目

在消费项目的 Git 根目录打开终端：

```console
cd /absolute/path/to/project
git rev-parse --show-toplevel
```

后续路径示例均假定当前目录是项目根目录。

## 2. 创建独立 workshop

项目中的固定路径 `.xcoding` 必须解析到一个 Git 工作树内，并且该工作树的仓库根目录必须不同于项目仓库根目录。不要把 workshop 历史放入业务源码仓库。

仅当项目中不存在 `.xcoding` 路径时，才运行下面的一个命令块。如果该路径已经存在，请先检查它的解析位置并保留对应 workshop，不要直接替换。

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

确认 Git 返回两个不同的顶层路径：

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

在显式用户门禁中提供决策，并让运行时公开接口负责节点调度、转换和检查点。代码和项目提交保留在项目仓库；work order 文档、feature 基线、运行时状态和节点 artifact 保留在独立 workshop 历史中。

继续查看[文档索引](../../index.md)，了解概念、工作流指引、编排细节和完整 Skill 参考。
