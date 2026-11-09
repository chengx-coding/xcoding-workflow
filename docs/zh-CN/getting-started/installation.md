# 安装

**语言：** [English](../../getting-started/installation.md) | **简体中文**

XC 的安装分为两个阶段，两个阶段有不同的执行者。先用 `uv` 校验不可变 release 并安装 `xcoding` 命令行；再由已安装的 CLI 为用户主目录或显式的消费项目安装 XC Skills 与 agent 定义。运行中的 CLI 不会安装自己的第一份副本。`xcoding install`、`xcoding upgrade` 与 `xcoding uninstall` 只是同一套 setup 事务（transaction）、清单（manifest）、恢复与回滚规则之上的生命周期入口；它们增加入口与报告，不引入第二个安装器或第二套状态模型。

## 前置条件

- Windows x86_64。这是唯一正式支持的平台；下文的[release 与支持矩阵](#release-与支持矩阵)给出权威的支持边界。
- CPython 3.12 或更高版本，正式验证基线为 CPython 3.12.13。
- `PATH` 中有 `uv`，用于隔离的工具安装。
- 若要使用工作流，至少需要一种受支持的 Agent 宿主：Codex、OpenCode、Claude Code 或 Trae。
- Git；如果希望 XC 自动保存工作区检查点，还需要配置 Git 身份。

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

## 两阶段 bootstrap

两个阶段有不同的执行者和不同的证据：

| 阶段 | 执行者 | 命令 | 结果 |
| --- | --- | --- | --- |
| 1. CLI | release 校验与 `uv` | `uv tool install <已验证 wheel>` | `PATH` 中的 `xcoding` 命令 |
| 2. 载荷 | 已安装的 `xcoding` 命令 | `xcoding install ...` | XC Skills、agent 定义与 setup 清单 |

CLI 阶段在任何 XC 命令存在之前运行。运行中的 CLI 不会、也无法安装自己的第一份副本。载荷阶段从已安装 wheel 的 Bundle 读取期望文件；它不会从源码检出复制，也不会替换 CLI。

这条边界在 Windows 上尤其重要。CLI 可以写入用户主目录或项目载荷，但替换或移除 CLI 本身属于外部 `uv` 操作。`xcoding upgrade --wheel` 以 `uv` 子进程启动该操作，并在 Windows 拒绝替换运行中程序时报告明确失败；`xcoding uninstall --all` 同样报告外部步骤边界，不会声称运行中的进程移除了自己。

## 获取并验证工具

从同一个不可变 GitHub Release 下载 wheel、`SHA256SUMS`、`provenance.json`、`integrity-manifest.json`、`release-notes.en.md` 和 `release-notes.zh-CN.md`。安装前，应确认 wheel 名称、大小、digest、distribution 版本、项目 commit 和 Bundle digest 与这些 release 文件一致。Candidate 专用 hash 属于 release asset，本项目文档有意不复制这些值。

安装已经验证的本地 wheel：

```console
uv tool install /absolute/path/to/xcoding_workflow-0.1.0-py3-none-any.whl
xcoding version --json
xcoding doctor --json
```

包含新快捷入口实现的构建也支持 `xcoding --version`；既有安装请继续使用 `xcoding version --json`，直到升级至包含该变更的构建。重新安装同一历史 wheel 不会增加该能力。

该阶段只创建 CLI。它不安装任何 Skill 或 agent 定义，此时也还没有 setup 清单。下文的载荷阶段从同一个 wheel 安装这些内容。

安装结果提供 `xcoding`，不提供 `xc` alias。XC 不分发 `install.ps1`、`install.sh`、远程脚本 pipe 命令或兼容 wrapper。不要从 PyPI 安装同名或近似名称的 package。

## 安装载荷

`xcoding install` 为一个作用域安装或对账载荷，选项如下：

```text
xcoding install [--scope user|project] [--project-root PATH] [--host HOST ...] [--dry-run] [--adopt-legacy] --json
```

`--scope` 默认 `user`。用户级作用域解析用户主目录，不接受 `--project-root`；项目级作用域要求显式 `--project-root`。`--host` 可以重复。省略时会选择固定的默认集合，即全部四种受支持宿主：`claude-code`、`codex`、`opencode`、`trae`。`--dry-run` 为零写入；`--adopt-legacy` 是下文描述的显式用户级旧布局迁移。

### 用户级作用域（默认）

```console
xcoding install --json
```

用户级作用域把载荷写入用户主目录，并记录在 `<home>/.agents/.xcoding-setup/manifest.json`。这与项目级 setup 使用同一份清单 schema，只有根目录不同。清单中的路径相对于用户主目录。

宿主标识和固定目标对每个根都相同：

| Host ID | Subagent 定义 | XC Skills |
| --- | --- | --- |
| `codex` | `.codex/agents` | `.agents/skills` |
| `opencode` | `.opencode/agents` | `.agents/skills` |
| `claude-code` | `.claude/agents` | `.claude/skills` |
| `trae` | `.trae/agents` | `.agents/skills` |

`.agents/skills` 由 `codex`、`opencode` 和 `trae` 共享。规划器会把每个目标解析为绝对路径，共享树只写一次，每个文件只有一份 owner 记录；选择三个宿主不会产生三份副本。因此，默认用户级安装也会在 `.opencode/agents` 尚不存在时创建它。若不需要，可用 `--host` 收窄宿主集合：

```console
xcoding install --host claude-code --host codex --json
```

Host set 是完整 desired state，不是增量添加列表。重复同一个 host 不会产生额外效果。后续安装成功时，新增 host 会安装其映射；省略以前选择的 host 时，只删除由该 host 单独拥有且未变化的路径。只要仍有任何所选 host 拥有共享 Skills，它们就会保留。未纳管文件永远不会被修改。

可以在零写入情况下检查确切计划：

```console
xcoding install --dry-run --json
```

Dry run 会报告 create、replace、remove 和 unchanged 操作以及采纳计划，并始终返回 `writes_performed: false`。报告的计划是真实写入计划，不是另一套估算。

### 旧布局采纳（仅用户级作用域）

0.3.6 开发安装器把所有权记录在两个旧清单中：`<home>/.agents/.xc-skill-install-manifest.json` 与 `<home>/.claude/.xc-skill-install-manifest.json`。`--adopt-legacy` 会显式迁移它们：

```console
xcoding install --scope user --adopt-legacy --json
```

采纳是显式的，普通 `install` 或 `upgrade` 都不会执行。它只适用于用户级作用域；项目级请求会以 `adopt_legacy_requires_user_scope` 拒绝。该步骤逐条用文件当前 SHA-256 校验旧记录，只认领与记录 hash 一致的字节。当前字节已经等于已安装 Bundle 的期望文件也会被认领，因此已经最新的副本不会变成冲突。新 Bundle 不再分发的已验证文件会变成删除操作，旧包（例如 `xc-change-report`）就是这样被移除的。漂移、缺失、非普通文件、不可读以及不属于所选宿主的记录会被保留并报告，而不是被覆盖或删除；两份清单都没有提到的未知内容不属于该事务，不会被触碰；唯一例外是 retired 包目录内生成的 `__pycache__`/`*.pyc`/`*.pyo` 缓存，清理会删除并报告它们。

事务提交后，旧 `expected_packages` 记录但新 Bundle 不再分发的包目录会被清理：生成的 `__pycache__` 内容与 `*.pyc`/`*.pyo` 文件会被删除，变空的目录会被修剪。旧清单没有记录的非缓存文件会被保留，并以原因 `unrecorded` 报告在 `adoption.cleanup` 摘要中，其包目录也会保留。同一摘要会报告 retired 包名、删除的缓存路径与数量、删除的目录、保留的未记录路径以及任何尽力而为的清理错误；清理警告不会把已提交的事务变成失败。

事务提交后，只有当某份旧清单的每一条记录都在作用域内且被认领时，才会把它归档到 setup 状态之外（`<home>/.agents/.xcoding-setup-legacy-<generation>/agents/` 或 `.../claude/`）。只要存在被保留的记录（未选择该宿主、漂移、缺失、非普通文件或不可读），该清单就会留在原处，因为它仍是这些字节唯一的所有权记录；结果会以 `archived: false` 和原因报告，之后的全宿主 `--adopt-legacy` 仍可读取它。采纳没有 `--force`；如果旧记录中的 hash 与当前文件不一致，该文件永远不会被认领或删除。

### 在项目中配置 Agent 宿主

`xcoding install --scope project --project-root /absolute/path/to/project --json` 是项目级 setup 引擎之上的薄别名。它要求显式存在项目根，把项目清单写到 `<project>/.agents/.xcoding-setup/manifest.json`，并保持 `xcoding setup` 的事务、清单 schema、恢复与回滚行为。它选择宿主的方式与用户级作用域相同：默认全部四种，可用 `--host` 收窄。

也可以继续直接使用 `xcoding setup`。它要求显式项目根和至少一个显式宿主；对需要保留的每个宿主重复 `--host`：

```console
xcoding setup --project-root /absolute/path/to/project --host codex --host opencode --host claude-code --host trae --json
```

每个所选宿主还会把其带版本的 `xc-delegation` capability statement 作为 package-owned setup 状态接收。Setup 会依据 Bundle 校验该声明，并报告 adapter version 与 security mode。当前 Claude Code、Codex、OpenCode 和 Trae 声明均为 `adapter_version=unverified`、`mode=validated-only`；不支持 network 与 secret grant。这些声明证明确定性准备流程的兼容性，不证明宿主 sandbox 强制执行。

`xcoding setup` 不会根据当前目录推断项目，也不会交互式检测宿主：项目根和至少一个宿主都必须显式给出。`xcoding install` 同样没有交互式宿主检测；省略 `--host` 时使用固定的四宿主默认集合，`--host` 只是显式收窄。旧布局采纳是显式且仅限用户级作用域的 `--adopt-legacy` 步骤。采纳没有 force 选项，也不会覆盖已经漂移的受管文件；`upgrade --force` 只用于重新安装同版本 wheel。

Workshop 仓库拓扑在 workshop-setup 步骤中选定（默认：独立工作区 `independent-link`），而非由 `xcoding setup` 或 `xcoding install` 选择。

## 写入前检查

追加 `--dry-run` 可以执行 Bundle 验证、根目录和路径安全检查、冲突检测、所有权规划与锁获取，同时不修改目标：

```console
xcoding install --scope user --dry-run --json
xcoding setup --project-root /absolute/path/to/project --host codex --host trae --dry-run --json
```

Dry run 会报告 create、replace、remove 和 unchanged 操作，并始终返回 `writes_performed: false`。如果 Bundle 无效、根或锁无法证明、目标跨越 link 或 reparse point、未纳管目标冲突、受管文件发生漂移，或存在意外 setup 状态，setup 与 install 会在 mutation 前关闭失败。应解决报告的 ownership 或路径问题；不要手工覆盖后盲目重试。

## 升级

`xcoding upgrade` 把载荷对账到已安装 CLI，并可选地先替换 CLI。与 `install` 一样，`--scope` 默认 `user`：

```text
xcoding upgrade [--scope user|project] [--project-root PATH] [--host HOST ...] [--wheel PATH] [--force] [--adopt-legacy] [--dry-run] --json
```

不带 `--wheel` 时，它把载荷对账到运行中的 CLI；所有操作都是 unchanged 时报告 `up-to-date`，有变化时报告 `reconciled`，dry run 报告 `dry-run`。它不会替换 CLI。

带 `--wheel` 时，它先读取 wheel 的 `.dist-info/METADATA` 中的 `Name` 与 `Version` 字段，校验分发包是 `xcoding-workflow` 且请求的版本可用。当 wheel 版本等于运行中 CLI 版本且没有 `--force` 时，CLI 阶段会被跳过并报告 `skipped-equal-version`，只对账载荷。否则它会执行 `uv tool install --force <wheel>`，再以 `xcoding install --scope ... --json` 调用新安装的 CLI 执行载荷阶段。在报告 `status: "upgraded"` 之前，载荷信封的 `version` 必须等于目标版本；当目标版本与运行版本不同时，其 Bundle hash 还必须不同于运行中的 Bundle（或等于 wheel 携带的 Bundle）。如果载荷阶段实际运行的是旧 CLI，就会以 `cli_upgraded_payload_failed` 失败；结果会同时报告 CLI 阶段与载荷结果。

`--force` 是 wheel 重装标志：当 wheel 版本与运行中 CLI 相同，它强制走 CLI 阶段而不是跳过。它不是采纳的 force，也永远不会覆盖已经漂移的受管文件。旧布局采纳始终是显式的：`install` 与 `upgrade` 都只在传入 `--adopt-legacy` 时才采纳；不带该标志的用户级 `upgrade` 永远不会采纳或归档旧记录（如果旧载荷中未纳管的字节与新 Bundle 冲突，则会以 `unmanaged_conflict` 关闭失败）。项目级作用域会拒绝 `--adopt-legacy`。

在当前进程运行期间，CLI 替换可能在 Windows 上失败。失败以结构化结果报告，绝不会报告为成功：

| Code | 含义 | 载荷写入 |
| --- | --- | --- |
| `cli_upgrade_failed` | `uv` 无法安装请求的 wheel。 | 无；载荷阶段不会开始。 |
| `cli_upgrade_requires_external_step` | `uv` 被运行中或已锁定的程序阻止，通常是 Windows 文件占用。关闭所有 `xcoding` 进程，再次运行报告中的 `uv tool install --force` 命令。 | 无；载荷阶段不会开始。 |
| `cli_upgraded_payload_failed` | CLI 已替换，但载荷安装失败、返回非零、返回不可用的信封，或没有运行目标 CLI 版本。安装并未完成；解决报告的载荷错误后重新运行 `xcoding upgrade` 或 `xcoding install`。 | 载荷阶段已开始并失败；结果非零。 |

`wheel_invalid`（路径缺失、不可读、不是 wheel、没有版本或分发包不正确）与 `uv_unavailable`（`PATH` 中没有 `uv`）也会在任何载荷写入之前报告。带不同 wheel 执行 `--dry-run` 时，结果会把 `uv tool install --force` 命令报告为 `would-run`，并把载荷计划推迟为 `deferred-until-cli-upgrade`，因为目标 Bundle 只有在新 CLI 安装后才存在；此时不会写入任何内容。

```console
xcoding upgrade --json
xcoding upgrade --wheel /absolute/path/to/<verified-wheel>.whl --json
xcoding upgrade --scope project --project-root /absolute/path/to/project --json
```

## 卸载

`xcoding uninstall` 移除一个作用域的载荷。与 `install` 一样，`--scope` 默认 `user`：

```text
xcoding uninstall [--scope user|project] [--project-root PATH] [--keep-state] [--all] [--dry-run] --json
```

载荷移除受 hash 守卫。命令读取 setup 清单，只有当路径由清单拥有且当前 SHA-256 仍等于记录 hash 时才删除文件；每次删除前都会重新校验 hash，因此计划之后发生变化的文件会中止移除，而不会删除新的字节。被修改的受管文件、非普通文件、`lark-*` 等用户自建 Skills、项目专属 Skills 与未知内容都会被保留并报告。空的受管包父目录会自底向上修剪；修剪停在宿主目标根，共享的 `.agents` 约定目录永远不会被删除。

真实移除载荷后，setup 状态目录会归档为 `<root>/.agents/.xcoding-setup-uninstalled-<generation>/`，而不是直接删除。`--keep-state` 保留完整归档，包括清单以及恢复所需的 `backup/` 与 `staging/` 数据。不带 `--keep-state` 时，默认在归档中写入 `receipt.json`，并删除 `backup/` 与 `staging/`，留下审计回执而不是完整备份。对同一根重复卸载是 no-op，报告 `installed: false` 且不执行写入。

没有 setup 清单但存在 0.3.6 旧清单的根不是 no-op。什么都没删除却仍有 XC 拥有的旧字节，属于假成功；因此 `uninstall` 会以 `legacy_payload_present` 和退出码 4 失败，报告旧布局摘要，并给出下一步 `xcoding install --scope user --adopt-legacy, then xcoding uninstall`。既没有 setup 清单也没有旧清单的干净根仍然报告 `installed: false` 且不写入任何内容。

不带 `--all` 时，命令只移除载荷，并明确报告剩余的 CLI 步骤：

```console
xcoding uninstall --json
```

结果包含 `cli_removal: "external-required"` 以及需要在外部运行的确切命令：`uv tool uninstall xcoding-workflow`。命令以退出码 0 结束，因为请求的载荷操作已完成，而 CLI 步骤并未被请求。

带 `--all` 时，它还会尝试该 `uv tool uninstall` 步骤。成功移除报告 `cli_removal: "removed"`。失败报告非零的 `cli_removal_failed` 结果，其中 `error.details.payload` 仍包含完整载荷结果；`error.details.cli_removal` 保持 `external-required`，并带有确切命令、返回码和有界输出。`--all --dry-run` 报告 `cli_removal: "dry-run"`，不启动任何进程。

运行中的 CLI 在 Windows 上无法删除自己。如果 `uv` 因为进程或 shell 仍占用工具而无法移除，应关闭所有 `xcoding` 进程，并在新 shell 中运行 `uv tool uninstall xcoding-workflow`。命令绝不会把失败的 CLI 移除报告为完全成功。

```console
xcoding uninstall --scope user --keep-state --json
xcoding uninstall --scope project --project-root /absolute/path/to/project --all --json
```

## 就绪检查

`xcoding doctor --json` 报告运行中的 CLI：`python`、`path`、`git`、`tk`、`bundle` 与 `delegation-adapters` 检查。追加 `--target-root` 还会针对该根运行 `target` 检查与只读 `payload` 检查：

```console
xcoding doctor --target-root <home> --json
xcoding doctor --target-root /absolute/path/to/project --json
```

Payload 检查读取 `<target-root>/.agents/.xcoding-setup/manifest.json`；只有该 setup 清单不存在时，它才会额外读取 `.agents/` 与 `.claude/` 下的两个旧 `.xc-skill-install-manifest.json`。它不写入、不取锁，也不认领任何内容。完全干净的目标两者都不存在：该检查为 `not-installed`、非必需，并给出 `payload-not-installed` warning，而不是失败。没有 setup 清单但至少存在一个旧清单的目标属于 0.3.6 布局，而不是干净机器：该检查为 `legacy`、必需、失败，令 `ready: false`，并以退出码 4 结束。它会报告旧清单路径、source revision、包与文件计数、逐清单错误、`legacy-install-detected` 问题，以及给出 `xcoding install --scope user --adopt-legacy` 的 `next_action`。如果 setup 清单存在，检查会把清单的版本与 Bundle hash 和运行中 CLI 比较，逐条校验清单拥有的文件，并把载荷分类为 `current`、`stale`、`missing`、`modified` 或 `invalid`；任何已安装但不是 `current` 的载荷同样会使该必需检查失败，令 `ready: false`，并以退出码 4 和错误码 `readiness-failed` 结束。

Payload 详情报告 generation、host set、清单版本与运行版本、清单 Bundle hash 与运行 Bundle hash、计数、Skills 与 agent 定义之间的 `kinds` 划分、带 preserved 文件说明的所有权计数，以及包含路径、期望与实际 hash、owner 和逐文件状态的 `problems` 列表。清单之外的文件报告为保留（preserved），不会被评估。只有旧布局的目标报告旧布局摘要，而不是 generation 与逐文件计数。针对 `<home>` 运行一次可以看到用户级载荷，针对项目根运行一次可以看到项目级载荷；两次运行的 CLI 检查相同。

## 受管升级与状态

每个生命周期命令都使用同一套事务引擎、同一份清单 schema 和同一个状态目录。`xcoding install` 与 `xcoding upgrade` 通过与 `xcoding setup` 相同的 staged transaction 写入；`xcoding uninstall` 归档同一份状态。没有任何命令会创建第二份清单或第二个事实源。

Setup 清单准确记录：

- `schema_version`——清单 schema 版本。
- `distribution`——`xcoding-workflow`。
- `version`——已安装 Bundle 版本。
- `bundle_manifest_sha256`——Bundle identity。
- `generation`——成功事务的 32 位十六进制 generation。
- `previous_generation`——回滚会恢复的 generation（存在时）。
- `hosts`——按规范顺序排列的完整所选 host set。
- `files`——逐文件记录，包含相对于根的路径、`mode`、SHA-256 与共享 owner 列表。

作用域不是清单字段；根目录决定作用域。用户级清单位于 `<home>/.agents/.xcoding-setup/manifest.json`，项目级清单位于 `<project>/.agents/.xcoding-setup/manifest.json`。

事务状态位于目标根下的同一个 `.agents/.xcoding-setup/` 目录：

- `manifest.json` 记录成功的 generation。
- `journal.json` 记录中断的事务，只在可能需要恢复时存在。
- `staging/` 保存进行中 generation 的 package-owned 事务数据。
- `backup/<generation>/` 保存回滚所需的上一代 generation 字节。

普通 setup 通过一个 staged transaction 同时承担首次安装和受管升级。它在接触目标前验证全部 desired bytes，持久记录 intent，使用原子替换，只在目标操作成功后发布所有权清单。中断事务会留下 durable state 供显式恢复使用，不会把部分工作伪装成成功。

Setup 与 install 只删除清单拥有且当前 identity 仍匹配已记录受管字节的路径。未纳管文件和漂移仍是用户拥有的冲突。Uninstall 会保留被修改的受管文件并报告，而不是删除它。

两个历史归档位于活动状态目录旁边，不属于当前状态模型：

- `.agents/.xcoding-setup-legacy-<generation>/` 在显式采纳后保存归档的旧清单。它创建在 `.agents/.xcoding-setup/` 之外，因此空闲状态校验保持不变。
- `.agents/.xcoding-setup-uninstalled-<generation>/` 在卸载后保存归档的状态目录，其中要么是完整备份（`--keep-state`），要么是回执且没有 backup/staging。

Install 是幂等的：紧接着重复运行只会报告 `unchanged` 操作。Uninstall 也是幂等的：重复运行报告 `installed: false` 且不写入。两个作用域都会为目标根获取共享的 setup 锁；并发操作会以 `setup_locked` 和退出码 4 被拒绝，而不是交错写入。

## 恢复与回滚

对项目根而言，setup 的恢复与回滚规则仍是受支持的控制。如果 setup 或 install 报告 `recovery_required`，应显式闭合中断 journal：

```console
xcoding setup --project-root /absolute/path/to/project --recover --json
```

Recovery 检查 durable journal；如果 manifest 已经提交，就完成该 transaction，否则恢复先前 generation。对于同一个可恢复状态，该操作是幂等的，并且不接受 `--host` 或 `--dry-run`。

需要恢复紧邻的上一份成功 generation 时，使用：

```console
xcoding setup --project-root /absolute/path/to/project --rollback --json
```

Rollback 同样拒绝 `--host` 和 `--dry-run`。只有有效的上一代 generation 存在且没有 open journal 需要 recovery 时，它才可用。两个操作都不会删除未拥有的文件，也不会覆盖已经漂移的受管 bytes。锁、identity、journal、backup 或 rollback 失败会保留为可机读错误并要求诊断，绝不会转化成 best-effort 破坏性清理。

用户级作用域不提供单独的回滚命令。真实卸载会把状态归档到 `.agents/.xcoding-setup-uninstalled-<generation>/` 以便检查与手工恢复，`--keep-state` 会保留完整备份。采纳归档的旧清单仍位于 `.agents/.xcoding-setup-legacy-<generation>/`；仍有保留字节的旧清单则留在其宿主根中。要从头恢复用户级载荷，重新安装已经验证的 wheel 并再次运行 `xcoding install --scope user`。

Capability statement 与 Agent、Skill 文件遵循同一套 transaction、recovery 和 rollback 规则。回滚到尚未包含这些声明的 generation 时，系统会明确报告为 `legacy-prompt` 兼容，不会伪装成支持 `prepared-profile`。`xcoding doctor --json` 把 delegation adapter 作为必需检查，报告已安装模式，并对每一份非 enforced 声明给出 warning。Skill 内部 profile 采用 current-only 格式，必须在不带根 `schema_version` 的情况下重新生成；旧 profile 文档会被拒绝，不会静默迁移。

## 从 0.3.6 开发安装器布局迁移

由 0.3.6 开发安装器准备过的用户主目录包含 `.agents/skills` 与 `.claude/skills` 树以及两个旧 `.xc-skill-install-manifest.json` 文件，但没有 `.agents/.xcoding-setup/manifest.json`。受支持的迁移是显式的，并会保留所有无法验证的文件。按顺序执行：

```console
uv tool install /absolute/path/to/xcoding_workflow-0.4.19-py3-none-any.whl
xcoding install --scope user --adopt-legacy --json
xcoding doctor --target-root <home> --json
```

1. 使用 `uv` 安装目标 wheel，与上文 CLI 阶段相同。
2. 运行显式用户级采纳。如果希望在写入前查看认领、删除和保留项，可以先加 `--dry-run` 查看计划。已验证的旧文件会被认领，新 Bundle 不再分发的包只在其 hash 匹配时删除，漂移或未知文件会被保留并报告。
3. 针对用户主目录运行只读 payload 检查。它必须报告载荷为 `current`。采纳之前它会报告 `legacy` 并使该必需检查失败，因为两个 0.3.6 清单仍然存在且尚无 setup 清单；这一失败正是执行上文采纳步骤的信号。

成功迁移后应为 25 个 `xc-*` Skill 包、没有 `xc-change-report` 包、存在 `xc-visual-design`，且所选宿主根中是当前 agent 定义——前提是 retired 包目录内没有遗留未被记录的非缓存文件。事务提交后，旧 `expected_packages` 记录但新 Bundle 不再分发的包会被清理：生成的 `__pycache__` 内容与 `*.pyc`/`*.pyo` 文件会被删除，变空的目录会被修剪。旧清单没有记录的非缓存文件会被保留，并以原因 `unrecorded` 报告在 `adoption.cleanup` 摘要中，其包目录也会保留；因此只有在没有这类文件遗留时，才成立 25 个包、无 `xc-change-report` 的终态。`lark-*`、`x-public-reader` 等既有的非 XC Skills 不会被触碰。结果会在 `adoption.preserved` 中报告保留的旧记录，并在 `adoption.cleanup` 中报告 retired 包的遗留内容。每条记录都被认领的旧清单会被移入 `.agents/.xcoding-setup-legacy-<generation>/`，旧树不再具有权威性；仍有保留记录的清单则留在原处并被报告，之后的全宿主采纳可在漂移解决后完成它。之后的卸载会归档新状态，而不会触碰这些归档。

如果采纳报告漂移，不要为了推进而删除文件。需要旧副本时，恢复记录中的字节；否则先把定制副本移出受管路径，再重新运行同一序列。不存在绕过 hash 检查的 force 选项。

`xcoding install`、`xcoding upgrade` 与 `xcoding uninstall` 是 CLI 及其载荷受支持的消费路径。当前检出的 `install_skills.py`、`skills/xc-workflow-evolution/scripts/install_xc_skills.py` 与 `build_agents.py` 仍是开发专用脚本；它们不是消费安装路径，也不会创建这里描述的 setup 清单。

## Skill 安装路径

`xcoding install` 是面向消费项目的受支持安装路径，默认用户级作用域，也可用 `--scope project --project-root` 指定项目级作用域。它从已安装的 wheel 安装所选宿主的 XC Skills 和 subagent 定义，并通过上文描述的 setup 事务、清单、恢复与回滚规则拥有这些文件。`xcoding upgrade` 与 `xcoding uninstall` 操作同一份受管载荷。

源码树内的安装器 [`install_skills.py`](../../../install_skills.py) 只是本检出使用的**开发路径**。它要求显式传入 `--target-skills`，从它所在的检出复制规范包，不属于 release 契约。它用于从这份源码树刷新开发目标，而不是安装受支持的消费项目。

该开发安装器只替换上一份 install manifest 拥有的、或规范源集合即将安装的 `xc-*` 包。manifest 不拥有、且规范源也不提供的 `xc-*` 目录在普通安装后会保留下来并被报告为 preserved；`--force` 才会替换它，而该选项只属于这条开发路径。它会把要替换的包删除后重新安装，因此不会把这些包的字节与上一份 manifest 比较；关闭失败的漂移规则属于 `install` 与 `setup` 使用的 `xcoding` setup 事务。

工作流演进开发安装器 `skills/xc-workflow-evolution/scripts/install_xc_skills.py` 与当前检出的 Skill 同步脚本 `build_agents.py` 是开发本仓库的维护工具。它们不会把 XC 安装到消费项目的用户主目录或项目中，公开安装路径也不依赖它们。

## 退出码与 JSON 输出

每个可机读的 `xcoding` 命令都要求显式 `--json`；唯一的独立例外是 `xcoding --version`，成功时打印 `xcoding <version>`。缺少 `--json` 会以退出码 2 和 `json-required` 错误结束，且不产生任何副作用。每个接受 `--json` 的命令只输出一个 JSON 信封：成功为 `{schema_version, ok: true, command, result}`；失败为 `{schema_version, ok: false, command, error: {code, message, details}}`。

| 退出码 | 含义 |
| --- | --- |
| 0 | 成功。对不带 `--all` 的 `uninstall`，表示载荷阶段成功，CLI 步骤报告为 `external-required`。 |
| 2 | 输入错误，包括 `invalid_arguments` 与 `json-required`。不会发生写入。 |
| 3 | Bundle 或已安装版本校验失败。 |
| 4 | 就绪或生命周期失败：`readiness-failed`、`managed_content_changed`、`unmanaged_conflict`、`legacy_manifest_conflict`、`legacy_manifest_invalid`、`legacy_payload_present`、`path_identity_changed`、`uninstall_archive_conflict`、`setup_locked`、`recovery_required`、`journal_invalid`、`project_root_required`、`project_root_not_allowed`、`host_unknown`、`adopt_legacy_requires_user_scope`、`wheel_invalid`、`uv_unavailable`、`cli_upgrade_failed`、`cli_upgrade_requires_external_step`、`cli_upgraded_payload_failed` 与 `cli_removal_failed`。 |
| 5 | 未归类的内部失败。 |

错误码在各命令间保持稳定。消费方应基于 `error.code` 分支并读取 `error.details`，而不是解析消息。对 `uninstall --all` 失败，`error.details.payload` 包含完整载荷结果，因此 CLI 移除失败不会丢弃载荷证据。

## 准备 Skill 内部 Worker

所属 `xc-*` Skill 可以在 `assets/workers/<profile-id>/profile.json` 定义私有 profile，并通过已经安装的 `xc-delegated-agent` 委派。[`xc-delegation` 公开契约](../../../skills/xc-delegation/SKILL.md)规定 profile、policy、overlay、adapter 与 envelope 输入。受支持的命令面如下：

```console
xcoding delegate validate-profile --skill-root /absolute/path/to/skill --profile-id read-only-evidence --json
xcoding delegate resolve-profile --skill-root /absolute/path/to/skill --profile-id read-only-evidence --json
xcoding delegate prepare --skill-root /absolute/path/to/skill --profile-id read-only-evidence --node-packet-json node.json --node-profile-ref-json profile-ref.json --project-policy-json project-policy.json --adapter-id codex --caller-constraints-json caller.json --out envelope.json --json
```

节点 packet 和 profile reference 来自 runtime 针对精确运行中 subagent attempt 的只读 `assignment-packet` 操作。只有成功的 `prepare` 结果可以设置 `dispatch_authoritative=true`。Validation、resolution、diagnostic compilation 与只读 `scan-legacy` 操作都不授权 dispatch。格式错误、过期、被拒绝、失效或不受支持的 v1 请求会停止，绝不会静默改走 `legacy-prompt`。

私有 profile 留在所属 Skill 内。若角色跨 Skill 共享、可由用户直接选择，或需要独立的持久模型或权限身份，应改用持久规范 Agent。

## 迁移已改名的 agent 定义

Canonical agent 定义在每个 host 下以一个文件名安装，而该文件名是每个安装过它的项目受管状态的一部分。原先以 `delegate-agent` 安装的 agent 定义现在是 `xc-delegated-agent`，因此安装过旧名的项目会看到每个所选 host 上一处删除与一处创建成对出现。host 根不变，只有安装文件名改变：

| Host ID | 变更前安装 | 变更后安装 |
| --- | --- | --- |
| `claude-code` | `.claude/agents/delegate-agent.md` | `.claude/agents/xc-delegated-agent.md` |
| `codex` | `.codex/agents/delegate-agent.toml` | `.codex/agents/xc-delegated-agent.toml` |
| `opencode` | `.opencode/agents/delegate-agent.md` | `.opencode/agents/xc-delegated-agent.md` |
| `trae` | `.trae/agents/delegate-agent.md` | `.trae/agents/xc-delegated-agent.md` |

该变更发生在升级到携带新名的 release 之后的下一次成功 `xcoding setup` 或 `xcoding install --scope project`。Setup 在同一个 transaction 内删除旧名文件并安装新名文件；共享 Skill 文件报告为 `unchanged`。该 transaction 不感知名称，它就是上文描述的普通 desired-state 协调作用在一个资源路径已改变的 Bundle 上。

先运行 dry run：

```console
xcoding setup --project-root /absolute/path/to/project --host codex --host opencode --host claude-code --host trae --dry-run --json
```

它把删除与创建报告成对操作，返回 `writes_performed: false`，且不改动任何文件。`--json` 在此不可省略：`xcoding` 的每个可机读命令都要求显式 `--json`，漏写会以退出码 2 和 `json-required` 错误结束，而不是返回计划。由于 dry run 会执行完整 preflight，它也会在写入任何内容之前报告下列阻塞条件。

Setup 只有在四个条件同时成立时才删除此前安装的文件：路径记录在所有权 manifest 中；路径不在由当前已安装 Bundle 与所选 host 集合算出的期望集合中；文件在磁盘上存在；它的 SHA-256 等于 manifest 记录。transaction 中没有任何其他操作能删除项目文件。

因此，迁移的消费方必须让旧名 agent 文件保持字节不变直到升级运行，且不得删除、移动或改名它：手工删除一个 manifest 拥有的文件会阻塞迁移，而不是帮助迁移。消费方也不得在新路径预先创建任何内容，即使它与包内定义逐字节相同。

下列每个条件都失败即拒绝，并且不执行任何写入。五个条件中有三个会在 `error.details.path` 中给出出问题的路径：`unmanaged_conflict` 与 `managed_content_changed` 的两种情形。`recovery_required` 与 `journal_invalid` 不报告路径：它们的错误信封携带空的 `details` 对象，因此解析 `error.details.path` 的消费方必须处理这两个条件下该字段缺失的情况。其中的 code 是机读错误信封里的 `error.code`，进程退出码为 4：

- `unmanaged_conflict`——新路径处已经存在文件，但它不被 manifest 拥有。项目级 setup 从不接管未纳管文件；唯一的采纳路径是显式的用户级 `--adopt-legacy` 旧布局迁移。
- `managed_content_changed`——manifest 拥有的文件字节不再等于已记录字节。对旧名 agent 文件的本地编辑会阻塞迁移。
- `managed_content_changed`——manifest 拥有的文件从磁盘上消失。手工删除旧名 agent 文件会阻塞迁移。
- `recovery_required`——存在中断 transaction 的 journal。普通 setup 拒绝并要求 `--recover`。
- `journal_invalid`——`--recover` 在与打开该中断 transaction 的 Bundle 不同的 Bundle 下运行，报文为 `recovery package Bundle differs from the interrupted transaction`。消费方在装回原 wheel 之前无法前进。

由于改变的是 wheel，应在升级之前用当前已安装的 wheel 关闭任何中断的 setup：

```console
xcoding setup --project-root /absolute/path/to/project --recover --json
```

如果先更换 wheel，`--recover` 会以 `journal_invalid` 失败，普通 setup 会以 `recovery_required` 失败，而且在原 wheel 装回之前两者都无法推进。

当已安装字节仍与清单一致时，`xcoding install` 会对账载荷；真实的采纳也能回收已验证的旧字节，但没有任何 force 或 adopt 选项会覆盖已经漂移的受管文件。如果受管文件被定制过，唯一受支持的补救是恢复该文件的安装字节；想保留的定制必须先移出受管路径。`--adopt-legacy` 是用户级旧布局迁移，不是项目级覆盖；`upgrade --force` 只控制同版本 wheel 的重装。

迁移成功后，旧名文件从每个已配置 host 根消失，新名文件出现，`.agents/.xcoding-setup/manifest.json` 列出新路径。旧名仍留在当前 generation 的回滚备份 `.agents/.xcoding-setup/backup/<generation>/` 中，而 `xcoding setup --rollback --json` 恢复紧邻的上一代 generation，也就是把旧名放回。它既不接受 `--host` 也不接受 `--dry-run`，并且在 journal 需要 recovery 时拒绝执行。Setup 也会保留腾空的 host 目录。因此，检索项目是否仍存在旧名的检查必须说明该名称在何处合法存在。消费方按 host 可见 emitted name 写下的引用，或在没有该字段的 host 上按文件名写下的引用，属于仓库无法检测的范围，由消费方自行更新。

### 本次改名的版本处置依据

历史决定：用户将此前改名判断为未破坏已文档化公开契约的兼容维护，并把数值升级推迟到后续发行，当时版本保持 `0.1.0`。判断依据是当时受跟踪契约未把已安装 agent 文件名或宿主可见 handle 明确列为契约条款；与维护政策的解释张力仍作为待复核依据保留。此决定不构成未来版本升级的批准或长期例外；后续迭代与累计未发布变更按[版本维护政策](../development/versioning.md)重新评估。

## Release 与维护政策

GitHub Releases 是 `0.1.0` 的唯一 release channel；PyPI、private index、远程安装脚本和其他 registry 不在契约内。Release 必须绑定一个不可变 tag、项目 commit、wheel digest、Bundle digest、精确 asset set、支持矩阵证据和双语 release notes。只有 candidate gate 通过且用户显式批准发布后才能 publication；这些安装文档不授权发布。

只对最新 `0.1.x` patch 提供 best-effort 维护。没有 SLA，也不保证向旧 patch backport。破坏已文档化公开契约的变更应进入 `0.2.0` 或更晚的 minor 版本，而不是 `0.1.x` patch。如果新的支持线取代 `0.1.x` 或维护终止，release notes 必须公告迁移或结束支持边界，并在两种语言中保留 rollback guidance。

继续阅读[快速开始](quick-start.md)，创建独立 workshop 并初始化其中的项目专用文档。
