# 安装

**语言：** [English (英文)](../../getting-started/installation.md) | **简体中文 (Simplified Chinese)**

从本地 xcoding-workflow 检出把工作流安装到消费端 Agent 宿主使用的 skills 目录。示例使用 `.agents/skills`；如果宿主使用其他发现目录，请替换为实际路径。

## 环境要求

需要 Git、带有 `pip` 的 Python，以及能够发现并调用 Skill 包的 Agent 宿主。如果受管 workshop 检查点被配置为创建提交，还需要有效的 Git 身份配置。

目前尚无正式的 Python 版本或 Agent 宿主兼容矩阵。仓库在 [`requirements.txt`](../../../requirements.txt) 中声明 Python 包依赖，但依赖声明不代表宿主支持保证。请在实际环境中验证所选 Python 运行时和 Agent 宿主。

## 安装仓库依赖

在 xcoding-workflow 检出目录中运行：

```console
python -m pip install -r requirements.txt
```

当前依赖包含工作流文档和模板工具所使用的 YAML 解析器。

## 完整替换式消费端安装

目标 skills 目录必须已经存在。

POSIX：

```sh
mkdir -p /absolute/path/to/consumer/.agents/skills
python install_skills.py --target-skills /absolute/path/to/consumer/.agents/skills
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force C:\absolute\path\to\consumer\.agents\skills | Out-Null
python install_skills.py --target-skills C:\absolute\path\to\consumer\.agents\skills
```

根目录的 `install_skills.py` 命令会有意破坏性替换目标 XC 包：

1. 删除目标中名称以 `xc-` 开头的每个目录。
2. 删除原有 XC 安装清单。
3. 从当前检出安装完整的规范 `xc-*` 包。
4. 对安装结果执行基于清单的验证。

这是**完整替换**，不是合并，也不是会保留本地修改的更新。运行前请备份或迁移仍需保留的目标 `xc-*` 修改。名称不以 `xc-` 开头的目录不受管理，也不会被删除。

## 受管的漂移感知安装

对于受管目标，请使用规范 [`xc-workflow-evolution` 契约](../../../skills/xc-workflow-evolution/SKILL.md)中记录的安装器。它会在显式目标根目录内的清单中记录源版本、源工作树状态、预期包集合和文件哈希。

目标根目录及其 `skills` 子目录必须已经存在：

```console
python skills/xc-workflow-evolution/scripts/install_xc_skills.py --source-root /absolute/path/to/xcoding-workflow --target-root /absolute/path/to/consumer/.agents --manifest /absolute/path/to/consumer/.agents/.xc-skill-install-manifest.json
```

使用以下只读命令验证源、清单和已安装包：

```console
python skills/xc-workflow-evolution/scripts/install_xc_skills.py --source-root /absolute/path/to/xcoding-workflow --target-root /absolute/path/to/consumer/.agents --manifest /absolute/path/to/consumer/.agents/.xc-skill-install-manifest.json --check
```

后续安装开始前，受管安装器会先把目标与现有清单进行比较。如果文件发生变化或缺失、出现意外文件或意外 `xc-*` 包，它会拒绝继续，而不会覆盖漂移。如果清单不存在，它会拒绝已经包含未纳管 `xc-*` 包的目标。检查通过后，它会替换完整的受管包集合，并且只删除旧清单中记录的过期 `xc-*` 包。非 `xc-*` 包始终不属于其管理范围。

根安装器创建的安装已经包含兼容清单，因此后续更新可以直接改用漂移感知命令。

## 消费端安装与开发镜像

消费项目应使用 `install_skills.py` 或受管安装器。不要把 `build_agents.py` 当作消费端安装命令。

`build_agents.py` 是仓库开发辅助脚本。它把当前检出 `skills/` 目录中的规范包镜像到同一检出使用的本地 Agent 发现目录，使贡献者能够在本地测试规范源变更；它不会以其他项目为目标，也不会建立受管消费端清单。

继续阅读[快速开始](quick-start.md)，创建独立 workshop 并初始化其中的项目专用文档。
