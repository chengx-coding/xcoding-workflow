# 安装

**语言：** [English](../../getting-started/installation.md) | **简体中文**

安装受支持的 XC release 时，先验证不可变 GitHub Release 中的 wheel，再使用 `uv` 安装 `xcoding` 工具，最后让 `xcoding setup` 在一个显式消费项目中管理所选 Agent 宿主。受支持的安装路径不提供 installer wrapper，也不使用单独的 Skill 安装命令。

## Release 与支持矩阵

第一份受支持的 distribution 契约是 `xcoding-workflow 0.1.0`，唯一 console command 是 `xcoding`。只有当不可变 GitHub Release 同时包含 wheel 以及匹配的完整性和 provenance 文件时，公开 release 才受支持。XC 不发布到 PyPI。

| 范围 | `0.1.0` 契约 | 证据边界 |
| --- | --- | --- |
| 操作系统 | Windows x86_64 | 这是唯一正式支持的平台。 |
| Python | CPython `>=3.12`；正式基线为 CPython `3.12.13` | Windows CPython `3.14.3` 可以具有 release smoke 证据，但其他可接受的新版本不属于正式基线。不支持非 CPython。 |
| Codex | Windows x86_64 上的 Codex CLI `0.145.0` | Release 证据必须证明 Skill 和 subagent 被真实发现、加载和执行；只检测 executable 不足以通过。 |
| OpenCode | Windows x86_64 上的 OpenCode `1.18.9` | 同样要求真实发现、加载和执行。 |
| Claude Code | Windows x86_64 上的 Claude Code `2.1.162` | 同样要求真实发现、加载和执行。 |
| Trae | Windows x86_64 上的 Trae CN `1.107.1` x64 | 同样要求真实发现、加载和执行。 |
| WSL | WSL2 Ubuntu 26.04 LTS x86_64 + CPython `3.14.4` | 仅提供实验性兼容 smoke 证据，不建立 native Linux 支持。 |
| Native Linux 与 macOS | `0.1.0` 不支持 | macOS 已推迟。未来支持需要单独批准的契约和真实 candidate 证据。 |

这张表定义 release gate，不表示尚未发布的 candidate 已经通过。如果不可变 release 及其绑定证据不存在，就没有受支持的公开 `0.1.0` 产物。

## 获取并验证工具

从同一个不可变 GitHub Release 下载 wheel、`SHA256SUMS`、`provenance.json`、`integrity-manifest.json`、`release-notes.en.md` 和 `release-notes.zh-CN.md`。安装前，应确认 wheel 名称、大小、digest、distribution 版本、项目 commit 和 Bundle digest 与这些 release 文件一致。Candidate 专用 hash 属于 release asset，本项目文档有意不复制这些值。

安装已经验证的本地 wheel：

```console
uv tool install /absolute/path/to/xcoding_workflow-0.1.0-py3-none-any.whl
xcoding version --json
xcoding doctor --json
```

安装结果提供 `xcoding`，不提供 `xc` alias。XC 不分发 `install.ps1`、`install.sh`、远程脚本 pipe 命令或兼容 wrapper。不要从 PyPI 安装同名或近似名称的 package。

## 在项目中配置 Agent 宿主

使用显式存在的项目根目录和至少一个显式宿主运行 setup。对需要保留的每个宿主重复 `--host`：

```console
xcoding setup --project-root /absolute/path/to/project --host codex --host opencode --host claude-code --host trae
```

宿主标识和项目相对目标固定如下：

| Host ID | Subagent 定义 | XC Skills |
| --- | --- | --- |
| `codex` | `.codex/agents` | `.agents/skills` |
| `opencode` | `.opencode/agents` | `.agents/skills` |
| `claude-code` | `.claude/agents` | `.claude/skills` |
| `trae` | `.trae/agents` | `.agents/skills` |

Host set 是完整 desired state，不是增量添加列表。重复同一个 host 不会产生额外效果。后续 setup 成功时，新增 host 会安装其映射；省略以前选择的 host 时，只删除由该 host 单独拥有且未变化的路径。只要仍有任何所选 host 拥有共享 Skills，它们就会保留。

Setup 不会根据当前目录推断项目，不会自动检测宿主，不会接管未纳管文件，也不提供 force 选项。

## 写入前检查

追加 `--dry-run` 可以执行 Bundle 验证、项目根目录和路径安全检查、冲突检测、ownership planning 与锁获取，同时不修改项目：

```console
xcoding setup --project-root /absolute/path/to/project --host codex --host trae --dry-run
```

Dry run 会报告 create、replace、remove 和 unchanged 操作，并始终返回 `writes_performed: false`。如果 Bundle 无效、项目根或锁无法证明、目标跨越 link 或 reparse point、未纳管目标冲突、受管文件发生漂移，或存在意外 setup 状态，setup 会在 mutation 前关闭失败。应解决报告的 ownership 或路径问题；不要手工覆盖后盲目重试。

## 受管升级与状态

普通 setup 通过一个 staged transaction 同时承担首次安装和受管升级。它在接触目标前验证全部 desired bytes，持久记录 intent，使用原子替换，只在目标操作成功后发布 ownership manifest。中断 transaction 会留下 durable state 供显式 recovery 使用，不会把部分工作伪装成成功。

项目内 transaction 状态位于 `.agents/.xcoding-setup/`：

- `manifest.json` 记录成功 generation、desired host set、Bundle identity、受管路径、hash 和共享 owner。
- `journal.json` 记录进行中的 transaction，只在可能需要 recovery 时存在。
- `staging/` 与 generation backup 保存安全完成或回滚所需的 package-owned transaction 数据。

不要通过编辑或删除这些文件来绕过失败。Setup 只删除 manifest 拥有且当前 identity 仍匹配已记录 managed bytes 的路径。未纳管文件和漂移仍是用户拥有的冲突。

## 恢复与回滚

如果 setup 报告 `recovery_required`，应显式闭合中断 journal：

```console
xcoding setup --project-root /absolute/path/to/project --recover
```

Recovery 检查 durable journal；如果 manifest 已经提交，就完成该 transaction，否则恢复先前 generation。对于同一个可恢复状态，该操作是幂等的，并且不接受 `--host` 或 `--dry-run`。

需要恢复紧邻的上一份成功 generation 时，使用：

```console
xcoding setup --project-root /absolute/path/to/project --rollback
```

Rollback 同样拒绝 `--host` 和 `--dry-run`。只有有效的上一代 generation 存在且没有 open journal 需要 recovery 时，它才可用。两个操作都不会删除未拥有的文件，也不会覆盖已经漂移的受管 bytes。锁、identity、journal、backup 或 rollback 失败会保留为可机读错误并要求诊断，绝不会转化成 best-effort 破坏性清理。

## Release 与维护政策

GitHub Releases 是 `0.1.0` 的唯一 release channel；PyPI、private index、远程安装脚本和其他 registry 不在契约内。Release 必须绑定一个不可变 tag、项目 commit、wheel digest、Bundle digest、精确 asset set、支持矩阵证据和双语 release notes。只有 candidate gate 通过且用户显式批准发布后才能 publication；这些安装文档不授权发布。

只对最新 `0.1.x` patch 提供 best-effort 维护。没有 SLA，也不保证向旧 patch backport。破坏已文档化公开契约的变更应进入 `0.2.0` 或更晚的 minor 版本，而不是 `0.1.x` patch。如果新的支持线取代 `0.1.x` 或维护终止，release notes 必须公告迁移或结束支持边界，并在两种语言中保留 rollback guidance。

继续阅读[快速开始](quick-start.md)，创建独立 workshop 并初始化其中的项目专用文档。
