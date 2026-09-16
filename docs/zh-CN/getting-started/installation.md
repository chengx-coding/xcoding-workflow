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
xcoding setup --project-root /absolute/path/to/project --host codex --host opencode --host claude-code --host trae --json
```

宿主标识和项目相对目标固定如下：

| Host ID | Subagent 定义 | XC Skills |
| --- | --- | --- |
| `codex` | `.codex/agents` | `.agents/skills` |
| `opencode` | `.opencode/agents` | `.agents/skills` |
| `claude-code` | `.claude/agents` | `.claude/skills` |
| `trae` | `.trae/agents` | `.agents/skills` |

每个所选宿主还会把其带版本的 `xc-delegation` capability statement 作为 package-owned setup 状态接收。Setup 会依据 Bundle 校验该声明，并报告 adapter version 与 security mode。当前 Claude Code、Codex、OpenCode 和 Trae 声明均为 `adapter_version=unverified`、`mode=validated-only`；不支持 network 与 secret grant。这些声明证明确定性准备流程的兼容性，不证明宿主 sandbox 强制执行。

Host set 是完整 desired state，不是增量添加列表。重复同一个 host 不会产生额外效果。后续 setup 成功时，新增 host 会安装其映射；省略以前选择的 host 时，只删除由该 host 单独拥有且未变化的路径。只要仍有任何所选 host 拥有共享 Skills，它们就会保留。

Setup 不会根据当前目录推断项目，不会自动检测宿主，不会接管未纳管文件，也不提供 force 选项。

Workshop 仓库拓扑在 workshop-setup 步骤中选定（默认：独立工作区 `independent-link`），而非由 `xcoding setup` 选择。

## Skill 安装路径

`xcoding setup` 是面向消费项目的受支持安装路径。它从已验证的 wheel 安装所选宿主的 XC Skills 和 subagent 定义，并通过下文描述的 transaction、manifest、recovery 与 rollback 规则拥有这些文件。

源码树内的安装器 [`install_skills.py`](../../../install_skills.py) 只是本检出使用的**开发路径**。它要求显式传入 `--target-skills`，从它所在的检出复制规范包，不属于 release 契约。它用于从这份源码树刷新开发目标，而不是安装受支持的消费项目。

该开发安装器只替换上一份 install manifest 拥有的、或规范源集合即将安装的 `xc-*` 包。manifest 不拥有、且规范源也不提供的 `xc-*` 目录在普通安装后会保留下来并被报告为 preserved；`--force` 才会替换它，而该选项只属于这条开发路径。它会把要替换的包删除后重新安装，因此不会把这些包的字节与上一份 manifest 比较；关闭失败的漂移规则属于 `xcoding setup`，见下文受管升级与状态一节。

## 就绪检查

当项目 setup 记录所指的某个 Skill 根目录缺少本应装有的包，或该包缺少其 assets 时，`xcoding doctor --target-root <project> --json` 会让其 `skill-packages` 检查失败，退出码 4，错误码 `readiness-failed`。既没有 setup 记录、也完全没有安装任何 XC 包的项目则通过检查，并由 `skill-packages-absent` 警告记录，因为不存在可以被判定为不完整的已安装 Skill 根目录。对受影响的宿主运行 `xcoding setup` 以恢复包；不要手工把文件复制进受管 Skill 根目录。

## 准备 Skill 内部 Worker

所属 `xc-*` Skill 可以在 `assets/workers/<profile-id>/profile.json` 定义私有 profile，并通过已经安装的 `xc-delegated-agent` 委派。[`xc-delegation` 公开契约](../../../skills/xc-delegation/SKILL.md)规定 profile、policy、overlay、adapter 与 envelope 输入。受支持的命令面如下：

```console
xcoding delegate validate-profile --skill-root /absolute/path/to/skill --profile-id read-only-evidence --json
xcoding delegate resolve-profile --skill-root /absolute/path/to/skill --profile-id read-only-evidence --json
xcoding delegate prepare --skill-root /absolute/path/to/skill --profile-id read-only-evidence --node-packet-json node.json --node-profile-ref-json profile-ref.json --project-policy-json project-policy.json --adapter-id codex --caller-constraints-json caller.json --out envelope.json --json
```

节点 packet 和 profile reference 来自 runtime 针对精确运行中 subagent attempt 的只读 `assignment-packet` 操作。只有成功的 `prepare` 结果可以设置 `dispatch_authoritative=true`。Validation、resolution、diagnostic compilation 与只读 `scan-legacy` 操作都不授权 dispatch。格式错误、过期、被拒绝、失效或不受支持的 v1 请求会停止，绝不会静默改走 `legacy-prompt`。

私有 profile 留在所属 Skill 内。若角色跨 Skill 共享、可由用户直接选择，或需要独立的持久模型或权限身份，应改用持久规范 Agent。

## 写入前检查

追加 `--dry-run` 可以执行 Bundle 验证、项目根目录和路径安全检查、冲突检测、ownership planning 与锁获取，同时不修改项目：

```console
xcoding setup --project-root /absolute/path/to/project --host codex --host trae --dry-run --json
```

Dry run 会报告 create、replace、remove 和 unchanged 操作，并始终返回 `writes_performed: false`。如果 Bundle 无效、项目根或锁无法证明、目标跨越 link 或 reparse point、未纳管目标冲突、受管文件发生漂移，或存在意外 setup 状态，setup 会在 mutation 前关闭失败。应解决报告的 ownership 或路径问题；不要手工覆盖后盲目重试。

## 受管升级与状态

普通 setup 通过一个 staged transaction 同时承担首次安装和受管升级。它在接触目标前验证全部 desired bytes，持久记录 intent，使用原子替换，只在目标操作成功后发布 ownership manifest。中断 transaction 会留下 durable state 供显式 recovery 使用，不会把部分工作伪装成成功。

项目内 transaction 状态位于 `.agents/.xcoding-setup/`：

- `manifest.json` 记录成功 generation、desired host set、Bundle identity、受管路径、hash 和共享 owner。它还记录 `report_package.name`、`report_package.template_file`，以及按宿主保存已安装 `xc-change-report` 包解析后绝对路径的 `report_package.paths.<host>`；报告阶段的挂载指令从该记录解析其子树模板，没有该记录的项目才回退到宿主到 Skill 根目录的对照表。
- `journal.json` 记录进行中的 transaction，只在可能需要 recovery 时存在。
- `staging/` 与 generation backup 保存安全完成或回滚所需的 package-owned transaction 数据。

不要通过编辑或删除这些文件来绕过失败。Setup 只删除 manifest 拥有且当前 identity 仍匹配已记录 managed bytes 的路径。未纳管文件和漂移仍是用户拥有的冲突。

## 恢复与回滚

如果 setup 报告 `recovery_required`，应显式闭合中断 journal：

```console
xcoding setup --project-root /absolute/path/to/project --recover --json
```

Recovery 检查 durable journal；如果 manifest 已经提交，就完成该 transaction，否则恢复先前 generation。对于同一个可恢复状态，该操作是幂等的，并且不接受 `--host` 或 `--dry-run`。

需要恢复紧邻的上一份成功 generation 时，使用：

```console
xcoding setup --project-root /absolute/path/to/project --rollback --json
```

Rollback 同样拒绝 `--host` 和 `--dry-run`。只有有效的上一代 generation 存在且没有 open journal 需要 recovery 时，它才可用。两个操作都不会删除未拥有的文件，也不会覆盖已经漂移的受管 bytes。锁、identity、journal、backup 或 rollback 失败会保留为可机读错误并要求诊断，绝不会转化成 best-effort 破坏性清理。

Capability statement 与 Agent、Skill 文件遵循同一套 transaction、recovery 和 rollback 规则。回滚到尚未包含这些声明的 generation 时，系统会明确报告为 `legacy-prompt` 兼容，不会伪装成支持 `prepared-profile`。`xcoding doctor --json` 把 delegation adapter 作为必需检查，报告已安装模式，并对每一份非 enforced 声明给出 warning。Skill 内部 profile 采用 current-only 格式，必须在不带根 `schema_version` 的情况下重新生成；旧 profile 文档会被拒绝，不会静默迁移。

## 迁移已改名的 agent 定义

canonical agent 定义在每个 host 下以一个文件名安装，而该文件名是每个安装过它的项目受管状态的一部分。原先以 `delegate-agent` 安装的 agent 定义现在是 `xc-delegated-agent`，因此安装过旧名的项目会看到每个所选 host 上一处删除与一处创建成对出现。host 根不变，只有安装文件名改变：

| Host ID | 变更前安装 | 变更后安装 |
| --- | --- | --- |
| `claude-code` | `.claude/agents/delegate-agent.md` | `.claude/agents/xc-delegated-agent.md` |
| `codex` | `.codex/agents/delegate-agent.toml` | `.codex/agents/xc-delegated-agent.toml` |
| `opencode` | `.opencode/agents/delegate-agent.md` | `.opencode/agents/xc-delegated-agent.md` |
| `trae` | `.trae/agents/delegate-agent.md` | `.trae/agents/xc-delegated-agent.md` |

该变更发生在升级到携带新名的 release 之后的下一次成功 `xcoding setup`。Setup 在同一个 transaction 内删除旧名文件并安装新名文件；共享 Skill 文件报告为 `unchanged`。该 transaction 不感知名称，它就是上文描述的普通 desired-state 协调作用在一个资源路径已改变的 Bundle 上。

先运行 dry run：

```console
xcoding setup --project-root /absolute/path/to/project --host codex --host opencode --host claude-code --host trae --dry-run --json
```

它把删除与创建报告成对操作，返回 `writes_performed: false`，且不改动任何文件。`--json` 在此不可省略：`xcoding` 的每个可机读命令都要求显式 `--json`，漏写会以退出码 2 和 `json-required` 错误结束，而不是返回计划。由于 dry run 会执行完整 preflight，它也会在写入任何内容之前报告下列阻塞条件。

Setup 只有在四个条件同时成立时才删除此前安装的文件：路径记录在所有权 manifest 中；路径不在由当前已安装 Bundle 与所选 host 集合算出的期望集合中；文件在磁盘上存在；它的 SHA-256 等于 manifest 记录。transaction 中没有任何其他操作能删除项目文件。

因此，迁移的消费方必须让旧名 agent 文件保持字节不变直到升级运行，且不得删除、移动或改名它：手工删除一个 manifest 拥有的文件会阻塞迁移，而不是帮助迁移。消费方也不得在新路径预先创建任何内容，即使它与包内定义逐字节相同。

下列每个条件都失败即拒绝，并且不执行任何写入。五个条件中有三个会在 `error.details.path` 中给出出问题的路径：`unmanaged_conflict` 与 `managed_content_changed` 的两种情形。`recovery_required` 与 `journal_invalid` 不报告路径：它们的错误信封携带空的 `details` 对象，因此解析 `error.details.path` 的消费方必须处理这两个条件下该字段缺失的情况。其中的 code 是机读错误信封里的 `error.code`，进程退出码为 4：

- `unmanaged_conflict`——新路径处已经存在文件，但它不被 manifest 拥有。Setup 从不接管未纳管文件。
- `managed_content_changed`——manifest 拥有的文件字节不再等于已记录字节。对旧名 agent 文件的本地编辑会阻塞迁移。
- `managed_content_changed`——manifest 拥有的文件从磁盘上消失。手工删除旧名 agent 文件会阻塞迁移。
- `recovery_required`——存在中断 transaction 的 journal。普通 setup 拒绝并要求 `--recover`。
- `journal_invalid`——`--recover` 在与打开该中断 transaction 的 Bundle 不同的 Bundle 下运行，报文为 `recovery package Bundle differs from the interrupted transaction`。消费方在装回原 wheel 之前无法前进。

由于改变的是 wheel，应在升级之前用当前已安装的 wheel 关闭任何中断的 setup：

```console
xcoding setup --project-root /absolute/path/to/project --recover --json
```

如果先更换 wheel，`--recover` 会以 `journal_invalid` 失败，普通 setup 会以 `recovery_required` 失败，而且在原 wheel 装回之前两者都无法推进。

不存在修复命令，也不存在 force 或 adopt 选项。如果受管文件被定制过，唯一受支持的补救是恢复该文件的安装字节；想保留的定制必须先移出受管路径。

迁移成功后，旧名文件从每个已配置 host 根消失，新名文件出现，`.agents/.xcoding-setup/manifest.json` 列出新路径。旧名仍留在当前 generation 的回滚备份 `.agents/.xcoding-setup/backup/<generation>/` 中，而 `xcoding setup --rollback --json` 恢复紧邻的上一代 generation，也就是把旧名放回。它既不接受 `--host` 也不接受 `--dry-run`，并且在 journal 需要 recovery 时拒绝执行。Setup 也会保留腾空的 host 目录。因此，检索项目是否仍存在旧名的检查必须说明该名称在何处合法存在。消费方按 host 可见 emitted name 写下的引用，或在没有该字段的 host 上按文件名写下的引用，属于仓库无法检测的范围，由消费方自行更新。

### 本次改名的版本处置依据

本次改名不被判定为破坏已文档化公开契约的变更，因此作为普通 `0.1.x` 补丁交付，而不是被路由到 `0.2.0` 或更晚的 minor 版本。这是一项记录在案的用户判断，且与上文的维护政策句子处于张力之中：本仓库中没有任何受跟踪明文把已安装 agent 文件名或 host 可见 agent handle 定为契约条款，本页也只记录 host 标识符及其项目相对目标根。该张力在此不化解。版本号及其载体不变：`pyproject.toml` 保持 `0.1.0`，任何版本提升都推迟到后续发布。

## Release 与维护政策

GitHub Releases 是 `0.1.0` 的唯一 release channel；PyPI、private index、远程安装脚本和其他 registry 不在契约内。Release 必须绑定一个不可变 tag、项目 commit、wheel digest、Bundle digest、精确 asset set、支持矩阵证据和双语 release notes。只有 candidate gate 通过且用户显式批准发布后才能 publication；这些安装文档不授权发布。

只对最新 `0.1.x` patch 提供 best-effort 维护。没有 SLA，也不保证向旧 patch backport。破坏已文档化公开契约的变更应进入 `0.2.0` 或更晚的 minor 版本，而不是 `0.1.x` patch。如果新的支持线取代 `0.1.x` 或维护终止，release notes 必须公告迁移或结束支持边界，并在两种语言中保留 rollback guidance。

继续阅读[快速开始](quick-start.md)，创建独立 workshop 并初始化其中的项目专用文档。
