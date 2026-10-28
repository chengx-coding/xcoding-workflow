# 工单示例：用 XC 构建一个 2D 沙盒

**语言：** [English](README.md) | **简体中文**

这是一个真实、完整的 XC 工单示例，不是截图导览：一个预先准备种子内容的消费项目被 DeepSeek Harness 命令行按受管生命周期完整推进，产物工单归档在这里，编排树由 runtime 渲染。示例还包含同一任务的第二次直接执行——不使用 XC——用来对照两种结果。

## 基本信息

| 项目 | 内容 |
| --- | --- |
| 任务 | 从零构建一个可离线游玩的 2D Minecraft 风格沙盒 |
| 为什么选它 | 常见的“模型能力”题目，结果可视、可检查，并且包含真实的设计决策 |
| 消费项目 | [`project/`](project/README.md)，由 [`seed/`](seed/) 种子构建出的最终静态页面 |
| 宿主 | DeepSeek Harness 命令行，`dsh headless` |
| 模型 | `deepseek-flash` |
| 入口 | `xc-work`，`operation=run`、`mode=change` |
| 展示的生命周期 | 准备、目标、分析、方案、方案确认闸门、实现、验证、结果 |
| 变更报告 | 示例中刻意豁免（`requires_report=false`、`report_skip_reason=user_waived`） |
| 工单 | `20261028-1731-implement-minecraft-sandbox` |
| 基线 | 用原始题目直接运行一次、不含任何工作流指令，产物在 [`baseline/`](baseline/) |

## 目录内容

```text
prompt.md                发给 DeepSeek Harness 的受管工单 Prompt
baseline-prompt.md       直接基线使用的原始题目 Prompt
setup/WORKFLOW.md        消费项目的桥接文档模板
setup/xc-orchestration-runtime.json  示例工作区的 runtime 配置
seed/                    工单开始时的种子快照
project/                 完成后的消费项目：交付的游戏
baseline/                直接基线：index.html、运行记录与最终回答
work-order/              归档工单：goal、analysis、solution、result、artifacts、runtime、tmp
tree/                    最终编排树的 SVG（可缩放）与 PNG（README 用图）
media/                   受管结果与基线页面各一张 960x600 截图
```

实际运行时，工单位于仓库之外一个独立的示例工作区 Git 仓库中，`project/.xcoding` 是指向它的目录联接。`work-order/` 是那个工单目录的副本（含 `tmp/` 临时文件）再加上运行的最终回答。副本中原本以 `.log` 结尾的文件改用 `.txt` 后缀并同步更新了引用，因为本仓库忽略 `*.log`；这些文件的行尾统一为 LF。那个活动工作区不属于本仓库。

## 为什么选这个任务

这个任务刻意为“新模型能力测试”那一类：从零写一个游戏。它结果可视，迫使实现做出真实决策（地形生成、碰撞、交互规则、相机、持久化），规模又足够在一个工单内完成。原始题目在 [`baseline-prompt.md`](baseline-prompt.md)；受管 Prompt 在同样的功能范围上增加了工作流指令与验证要求。

## 工单是怎么跑的

1. 消费项目先准备好种子：页面壳、小型模块骨架、Node 测试入口和 Python 页面检查；种子快照归档在 [`seed/`](seed/)。沙盒功能全部未实现。
2. 在仓库之外创建一个独立的示例工作区 Git 仓库，把桥接模板与 runtime 配置复制进它的 `.xcoding`，再把 `project/.xcoding` 联接过去。
3. 从 XC 检出根目录启动：

   ```powershell
   $env:DEEPSEEK_API_KEY = "<harness 凭据存储中的 key>"
   $env:DSH_PERMISSION_MODE = "danger-full-access"
   Get-Content samples/minecraft-sandbox-work-order/prompt.md -Raw | dsh headless -
   ```

   无头配置要求 API key。权限模式在这台机器上也是必需的：默认的 `workspace-write` 沙箱无法完成 Windows ACL 设置，所有 shell 调用都会在启动前被拒绝。
4. 工单在变更报告被明确豁免、且不创建项目 Git 提交的情况下关闭；提交由外层仓库统一完成。运行日志的最终回答保留在 [`work-order/dsh-run.txt`](work-order/dsh-run.txt)。

Prompt 是为无头会话写的：禁止向用户提问，要求主会话记录决定并批准方案闸门，并且所有 runtime 访问只能走公开的 `xcoding runtime` 接口。

## 读编排树

![完成的工单编排树](tree/orchestration-tree.png)

PNG 是 Viewer 自带的导出，按原始尺寸栅格化。可缩放的独立版本是 [`tree/orchestration-tree.svg`](tree/orchestration-tree.svg)。树里能看到完整生命周期：准备、目标、分析、方案与方案确认闸门、实现、验证、结果与 finalizer，以及负责写入和校验每份文档的 document-evolution 子树。

两处细节值得说明：

- **报告组是跳过，不是缺失。** 标题为 “Produce change review report” 的节点状态是 `skipped`，因为用户明确豁免了变更报告环节。豁免记录在工单里（`work_order.requires_report=false`、`work_order.report_skip_reason=user_waived`）。
- **pending 节点是不可达分支。** 16 个节点被跳过，8 个仍是 pending。被跳过的是条件分支本身：四个文档评审循环、四个文档闸门、四个不通过的恢复组、reconciliation 组、clarification 组、solution 恢复组和报告组。8 个 pending 节点是四个被跳过评审循环的子节点，它们从未运行。树以 30 个成功节点封存（17 个可执行任务叶子加一个闸门，其余是组合节点），因此这些 pending 节点是“从未被调度”，不是“没有做完”。

归档的 runtime 树报告 `status=complete`，SHA-256 完整性校验通过。工单文档在 [`work-order/`](work-order/)： [`goal.md`](work-order/goal.md)、[`analysis.md`](work-order/analysis.md)、[`solution.md`](work-order/solution.md)、[`result.md`](work-order/result.md)。验证证据在 [`work-order/artifacts/verification/verification.md`](work-order/artifacts/verification/verification.md)。

## 工单产出了什么

交付页面是 [`project/index.html`](project/index.html)，由七个 JavaScript 模块和六个测试文件支撑。实现包括：

- 确定性的种子地形，含草、土、石与树木；
- 带重力、跳跃、水平碰撞与分步瓦片碰撞的玩家；
- 左键挖掘、右键放置，含触及距离、空格、支撑与玩家重叠规则；
- 四格物品栏，支持数字键与点击选择；
- 跟随玩家并夹在世界边界内的相机；
- 用 `localStorage` 保存和恢复世界、玩家与选择；
- 供自动检查读取的页面状态标记。

在 `project/` 下复现验证：

```text
node --test "tests/**/*.test.js"   28 个测试，28 通过
python tools/page_check.py         静态检查通过；状态标记为绿色；53 个颜色桶
```

下面对比图里的受管结果截图是 [`media/xc-sandbox.png`](media/xc-sandbox.png)。

## 直接基线与对比

启动会话使用同一模型（`deepseek-flash`）、同一台机器和原始题目 Prompt，不做任何工作流干预，直接运行一次。基线在 XC 检出之外运行，因此检出的 `xc-*` Skills 不在工作目录中；harness 的全局 Skill 发现未被探测。启动配置与最终回答记录在 [`baseline/run.md`](baseline/run.md) 和 [`baseline/dsh-run.txt`](baseline/dsh-run.txt)；内部转录没有归档。

| 直接基线 | XC 工单 |
| --- | --- |
| <img src="media/baseline-sandbox.png" alt="直接基线沙盒截图" width="440"> | <img src="media/xc-sandbox.png" alt="XC 工单沙盒截图" width="440"> |

可核对的事实：

| 事实 | 直接基线 | XC 工单 |
| --- | --- | --- |
| 交付结构 | 1 个文件 | 17 个文件（页面、CSS、7 个模块、6 个测试、工具、README） |
| 总字节数 | 98,883 | 69,035 |
| 提交的逻辑测试 | 0 | 28 个，全部通过 |
| 自动页面检查 | 无 | 状态标记绿色，53 个颜色桶 |
| 页面实际引用的外部资源 | 0 | 0 |
| 截图颜色桶 | 203 | 53 |
| 持久过程记录 | 无 | 完整工单 |

两张截图的差异很直接。直接基线明显更精致：带品牌标题栏、种子与自动保存指示、Help 与 New World 按钮、草/沙/石分层地形、远山、八格物品栏与每格数量、底部操作提示。受管结果是一个更小、更朴素的页面：四格物品栏和两行 HUD 面板（操作提示与当前选择）。

所以在这一对单次运行里，工作流**没有**产出更好看或功能更多的游戏。它增加的是可验证性与可追溯性：提交的测试、可重复的页面检查、写下来的架构、验证记录和完整的工单历史。直接基线增加了视觉打磨与额外功能；它的 Prompt 只要求游戏，而受管 Prompt 还要求测试、文档与验证。

这个对比的局限：双方各一次运行、同一启动配置、Prompt 不同（受管 Prompt 还要求测试、文档和验证）、没有盲评。它只是记录这里实际发生的事，不能证明 XC 会普遍提升或降低模型输出。一个值得做的后续实验是给受管 Prompt 加上视觉验收标准，看这个表现差距会不会消失。

## 自己复现

前置条件：Python 3.12、Node.js 24、Google Chrome、Git，以及为宿主安装好的 `xcoding` 包与 XC Skills。在仓库根目录执行：

```powershell
$Checkout = (Get-Location).Path
$Sample = Join-Path $Checkout "samples/minecraft-sandbox-work-order"
$Workshop = Join-Path (Split-Path $Checkout -Parent) "minecraft-sandbox-workshop"

# 仓库里的 project/ 是完成后的结果；用一份干净的种子替换它。
if (Test-Path "$Sample/project/.xcoding") { [System.IO.Directory]::Delete("$Sample/project/.xcoding", $false) }
Remove-Item "$Sample/project" -Recurse -Force
New-Item -ItemType Directory -Force "$Sample/project" | Out-Null
Copy-Item "$Sample/seed/*" "$Sample/project/" -Recurse -Force

New-Item -ItemType Directory -Force (Join-Path $Workshop ".xcoding") | Out-Null
git -C $Workshop init
Copy-Item "$Sample/setup/WORKFLOW.md" (Join-Path $Workshop ".xcoding/WORKFLOW.md")
Copy-Item "$Sample/setup/xc-orchestration-runtime.json" (Join-Path $Workshop ".xcoding/xc-orchestration-runtime.json")
New-Item -ItemType Junction -Path (Join-Path $Sample "project/.xcoding") -Target (Join-Path $Workshop ".xcoding")

$env:DEEPSEEK_API_KEY = "<harness 凭据存储中的 key>"
$env:DSH_PERMISSION_MODE = "danger-full-access"
Get-Content $Sample/prompt.md -Raw | dsh headless -
```

这个重置会删除完成后的文件与可能残留的 `.xcoding` 联接，再复制种子；工作区步骤会重新创建联接。不重置的话，重跑会从完成后的项目开始，而不是从任务起点开始。

运行报告完成后，工单位于 `$Workshop/.xcoding/work-orders/<work-order-id>/`。渲染它的树：

```powershell
$Tree = "$Workshop/.xcoding/work-orders/<work-order-id>/runtime/orchestration.xml"
$viewer = xcoding viewer --tree $Tree --no-browser | ConvertFrom-Json
$svg = Invoke-WebRequest "$($viewer.url)api/trees/$($viewer.trees[0].tree_id)/svg"
[IO.File]::WriteAllBytes("orchestration-tree.svg", [Text.Encoding]::UTF8.GetBytes($svg.Content))
```

本示例里的 `work-order/` 是原始工作区目录的副本再加上运行的最终回答，其中原本以 `.log` 结尾的文件改为 `.txt` 并统一为 LF；因此里面的绝对路径来自原始运行。

## 局限

- 这是单次示例运行，只记录一次执行，不是基准测试。
- `seed/` 是起始快照的重建，不是从原始运行中逐字节恢复的副本；完成后的 `project/` 与归档工单才是原始产物。
- 基线 Prompt 与受管 Prompt 按设计不同；受管运行还必须满足测试、文档和验证要求。
- 两个结果都没有人工试玩；检查是自动化加上截图查看。
- 页面检查工具属于示例的消费项目，不是 XC 的通用能力。
- 工作流契约在 [`docs/zh-CN/`](../../docs/zh-CN/index.md)；本示例只做演示，不定义也不扩展这些契约。
