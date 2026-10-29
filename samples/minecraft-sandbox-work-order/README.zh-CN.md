# 工单示例：用 XC 构建一个 2D 沙盒

**语言：** [English](README.md) | **简体中文**

这是一个真实、完整的 XC **create 模式**工单示例，不是截图导览：一个预先准备种子内容的消费项目被 DeepSeek Harness 命令行按受管生命周期完整推进，产物工单归档在这里，编排树由 runtime 渲染。示例还包含同一任务的第二次直接执行——不使用 XC——用来对照两种结果。

这一版示例使用工作流的**动态 scope policy**：任务是从零创建，所以用 `xc-work` 的 `mode=create`，没有最小化预设，并在 goal 中写明用户可见质量契约。analysis、solution 和变更报告被刻意省略；create 生命周期是 goal、implementation、带独立视觉评审的 verification、result。

## 基本信息

| 项目 | 内容 |
| --- | --- |
| 任务 | 从零构建一个可离线游玩的 2D Minecraft 风格沙盒 |
| 为什么选它 | 常见的“模型能力”题目，结果可视、可检查，并且包含真实的设计决策 |
| 消费项目 | [`project/`](project/README.md)，由 [`seed/`](seed/) 种子构建出的最终静态页面 |
| 宿主 | DeepSeek Harness 命令行，`dsh headless` |
| 模型 | `deepseek-flash` |
| 入口 | `xc-work`，`operation=run`、`mode=create` |
| Scope policy | create：无最小化预设；goal 中携带用户可见质量契约 |
| 展示的生命周期 | 准备、目标、实现、验证、独立视觉评审、结果 |
| 刻意省略 | 分析、方案、方案闸门、变更报告 |
| 质量 bar | 至少与一次强 one-shot 尝试同样精致、同样丰富 |
| 工单 | `20261029-1219-2d-sandbox-game` |
| 基线 | 用原始题目直接运行一次、不含任何工作流指令，产物在 [`baseline/`](baseline/) |

## 目录内容

```text
prompt.md                发给 DeepSeek Harness 的 create 模式受管 Prompt
baseline-prompt.md       直接基线使用的原始题目 Prompt
setup/WORKFLOW.md        消费项目的桥接文档模板
setup/xc-orchestration-runtime.json  示例工作区的 runtime 配置
seed/                    工单开始时的种子快照
project/                 完成后的消费项目：交付的游戏
baseline/                直接基线：index.html、运行记录与最终回答
work-order/              归档的 create 工单：goal、评审/验证 artifact、result、runtime、tmp
                         （没有 analysis、solution 或 report）
tree/                    最终编排树的 SVG（可缩放）与 PNG（README 用图）
media/                   受管结果与基线页面各一张 960x600 截图
```

实际运行时，工单位于仓库之外一个独立的示例工作区 Git 仓库中，`project/.xcoding` 是指向它的目录联接。`work-order/` 是那个工单目录的副本（含 `tmp/` 临时文件）再加上运行的最终回答 `work-order/dsh-run.txt`。那个活动工作区不属于本仓库。

## 为什么选这个任务

这个任务刻意为“新模型能力测试”那一类：从零写一个游戏。它结果可视，迫使实现做出真实决策（地形生成、碰撞、交互规则、相机、持久化），规模又足够在一个工单内完成。原始题目在 [`baseline-prompt.md`](baseline-prompt.md)；受管 Prompt 在同样的功能范围上增加了工作流指令、质量契约与验证要求。

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
4. 工单以 create 模式运行：准备与 goal（含质量契约）、一个实现子树（构建页面与测试）、验证、独立视觉评审、对最终文件的再次检查，以及结果。变更报告被明确豁免，且不创建项目 Git 提交；提交由外层仓库统一完成。最终回答保留在 [`work-order/dsh-run.txt`](work-order/dsh-run.txt)。
5. Prompt 是为无头会话写的：禁止向用户提问，要求主会话记录自己的决定，并且所有 runtime 访问只能走公开的 `xcoding runtime` 接口。

## 读编排树

![完成的 create 模式工单编排树](tree/orchestration-tree.png)

PNG 是从 Viewer 的 SVG 导出的完整树，按原始尺寸渲染。可缩放的独立版本是 [`tree/orchestration-tree.svg`](tree/orchestration-tree.svg)。树里能看到 create 生命周期：准备、目标、实现（构建、验证、独立评审、再次检查）、结果与 finalizer。analysis、feature reconciliation、clarification、solution、approval 和 solution recovery 分支都被跳过，变更报告组也被跳过。树以 14 个成功节点、7 个跳过节点封存，没有 pending 工作。

归档的 runtime 树报告 `status=complete`，SHA-256 完整性校验通过。工单文档在 [`work-order/`](work-order/)：[`goal.md`](work-order/goal.md) 与 [`result.md`](work-order/result.md)。实现证据在 [`work-order/artifacts/implementation/sandbox.md`](work-order/artifacts/implementation/sandbox.md)，独立视觉评审在 [`work-order/artifacts/review/visual-review.md`](work-order/artifacts/review/visual-review.md)，验证在 [`work-order/artifacts/verification/acceptance.md`](work-order/artifacts/verification/acceptance.md) 与 [`work-order/artifacts/verification/final-recheck.md`](work-order/artifacts/verification/final-recheck.md)。

## 工单产出了什么

交付页面是 [`project/index.html`](project/index.html)，由本地 CSS、八个 JavaScript 模块和五个测试文件支撑。实现包括：

- 确定性的种子地形，含 meadow、woodland、dune 三种生物群系，分层草、土、石与基岩，洞穴、煤、prism crystal、树木、近出生点树林、路旁灯笼和远景森林层；
- 带重力、加速度、冲刺、可变高度跳跃、coyote time 和分轴实体碰撞的玩家；
- 有触及距离的左键挖掘、面向感知的右键放置，含目标括号、方块 ghost、玩家重叠拒绝和明确的受阻反馈；
- 九格物品栏，支持数字键与滚轮选择，凸起/发光的选中态，以及方块图标与名称；
- 平滑跟随、受世界边界限制的相机；带视口框的 survey minimap；含星星、太阳、月亮、云、视差山脊、鸟和萤火虫的昼夜天空；洞穴蘑菇、灯笼/水晶光、破坏/放置粒子、相机震动和生成的 Web Audio 反馈；
- 带版本的 `localStorage` 持久化：世界、种子、玩家位置、选中格、时间和进度，并对缺失、损坏或过期存档安全回退；
- field-notes 清单、种子/时间/坐标信息条、保存状态、完整 field manual、基于种子生成新世界的 New World 对话框，以及紧凑的控制说明。

从 `project/` 复现的验证：

```text
node --test "tests/**/*.test.js"   34 个测试，34 通过
python tools/page_check.py --window 960x600
                                   静态/网络检查通过；状态标记为绿；
                                   渲染画布 285 个颜色桶
```

下方使用的截图是 [`media/xc-sandbox.png`](media/xc-sandbox.png)。

## 直接基线与对比

启动会话使用同一模型（`deepseek-flash`）、同一台机器和原始题目，在没有工作流的情况下直接运行了一次。基线在 XC 检出之外运行，因此工作目录里没有本 checkout 的 `xc-*` Skills。启动配置与最终回答记录在 [`baseline/run.md`](baseline/run.md) 和 [`baseline/dsh-run.txt`](baseline/dsh-run.txt)；内部 transcript 未归档。

| 直接基线 | XC create 模式工单 |
| --- | --- |
| <img src="media/baseline-sandbox.png" alt="直接基线沙盒截图" width="440"> | <img src="media/xc-sandbox.png" alt="XC create 模式沙盒截图" width="440"> |

可测事实：

| 事实 | 直接基线 | XC create 模式工单 |
| --- | --- | --- |
| 交付布局 | 1 个文件 | 17 个文件（页面、CSS、8 个模块、5 个测试、工具、README） |
| 服务页面字节 | 98,883 | 132,680 |
| 项目总字节 | 98,883 | 168,758 |
| 提交的逻辑测试 | 0 | 34，全部通过 |
| 自动页面检查 | 无 | 状态标记为绿，285 个颜色桶 |
| 服务文件中的外部引用 | 0 | 0 |
| 截图颜色桶 | 203 | 285 |
| 持久过程记录 | 无 | 完整 create 工单 |
| 独立视觉评审 | 无 | 通过强 one-shot 参照 |

受管结果现在有更强的视觉身份和更宽的功能集：填满窗口的 field-journal 界面、“Verdant Depths” 字标、survey minimap、field-notes 清单、昼夜天空、九格物品栏、洞穴/水晶光、粒子，以及清楚的放置/拒绝反馈。直接基线仍有干净的品牌标题栏和紧凑 HUD，但没有 minimap、field notes、昼夜循环、同样的方块种类或交互反馈。按可测事实和截图，create 模式结果至少与基线持平，并且明显更丰富。

这是**动态 scope policy** 的结果：上一版示例把创建任务当作 `change` 并套用强最小化规则，结果很薄；这一版使用 `create`、质量契约和独立视觉评审，产品不再被封顶在“最小扩展”。示例不声称 XC 普遍提升模型输出；它记录的是这条策略在这一个任务上产生的结果。

对比的限制：每侧只跑一次、启动配置相同、Prompt 不同（受管 Prompt 还要求测试、文档、验证和质量 bar）、静态截图对比、没有人类试玩。这是对这一次运行的记录，不是受控 benchmark。

## 复现

前置条件：Python 3.12、Node.js 24、Google Chrome、Git，以及为宿主安装的 `xcoding` 包和 XC Skills。从仓库根目录：

```powershell
$Checkout = (Get-Location).Path
$Sample = Join-Path $Checkout "samples/minecraft-sandbox-work-order"
$Workshop = Join-Path (Split-Path $Checkout -Parent) "minecraft-sandbox-workshop"

# 已提交的 project 是完成结果；先替换为干净的种子副本。
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

重置会删除完成文件与旧 `.xcoding` 联接，再复制种子；工作区步骤创建新的联接。没有这一步，重跑会从完成项目开始，而不是任务的起点。

运行报告完成后，工单位于 `$Workshop/.xcoding/work-orders/<work-order-id>/`。渲染其树：

```powershell
$Tree = "$Workshop/.xcoding/work-orders/<work-order-id>/runtime/orchestration.xml"
$viewer = xcoding viewer --tree $Tree --no-browser | ConvertFrom-Json
$svg = Invoke-WebRequest "$($viewer.url)api/trees/$($viewer.trees[0].tree_id)/svg"
[IO.File]::WriteAllBytes("orchestration-tree.svg", [Text.Encoding]::UTF8.GetBytes($svg.Content))
```

归档的 `work-order/` 是原始工作区目录加上最终回答的副本，行尾统一为 LF；因此它包含原始运行的绝对路径。

## 局限

- 这是单次示例运行，记录一次执行，不是 benchmark。
- `seed/` 是起始快照的重建，不是原始运行的逐字节恢复；完成的 `project/` 与归档工单是原始产物。
- 基线与受管 Prompt 按设计不同；受管运行还要满足测试、文档、验证和质量契约。
- 两侧都没有人类试玩；检查是自动化加截图审视。独立视觉评审是静态的，不是实时响应式或声学评审。
- 页面检查工具属于示例的消费项目，不是通用 XC 能力。
- 工作流契约在 [`docs/`](../../docs/index.md)；本示例只展示它们，不定义或扩展它们。
