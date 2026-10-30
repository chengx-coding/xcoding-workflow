# 工单示例：通过 XC 构建的 2D 沙盒（0.3.6）

**语言：** [English](README.md) | **简体中文**

这是一个真实、完整的 XC **标准 create 模式**工单，已从 0.3.6 运行提升为公开示例。一个带种子的
消费者项目通过 DeepSeek Harness 命令行走完正常受管生命周期，产出的工单归档在这里；同一任务的
一次无 XC 直接运行也保留下来用于对比。

0.3.6 使用完整生命周期——goal、analysis、solution、solution approval、implementation、
verification、result——并启用 create 范围保真、reference signature 和 prior capability
preservation 契约。变更报告按用户要求豁免。运行与 one-shot baseline、所有历史实现隔离：工作区
只包含 workflow Skills、seed 项目和桥接，prompt 禁止读取 baseline 或任何 prior implementation。

## 快速事实

| 项目 | 值 |
| --- | --- |
| 任务 | 从零构建可玩、离线的 2D Minecraft 风格沙盒 |
| 版本 | **0.3.6**（当前标准 sample；v1.1 体验排名第 4） |
| 消费者项目 | [`project/`](project/README.md)，从 [`seed/`](seed/) 构建 |
| 宿主 | DeepSeek Harness CLI，`dsh headless` |
| 模型 | `deepseek-flash` |
| 入口 | `xc-work`，`operation=run`，`mode=create` |
| 生命周期 | goal、analysis、solution、approval、implementation、verification、result |
| 有意省略 | 变更报告（用户明确豁免） |
| 质量 bar | 至少与强 one-shot 一样精致/丰富；reference signature；保留 prior capabilities |
| 隔离 | 运行工作区无 sample、baseline、prior result 或已有实现 |
| 工单 | `20261030-0000-minecraft-sandbox` |
| 归档树 | [`work-order/runtime/minecraft-sandbox.svg`](work-order/runtime/minecraft-sandbox.svg) |
| Baseline | 无 workflow 的原始 prompt 直接运行，见 [`baseline/`](baseline/) |

## 目录内容

```text
prompt.md                 0.3.6 运行使用的标准 create prompt
baseline-prompt.md        直接 baseline 使用的原始任务 prompt
setup/                    消费者工作坊的项目桥接与运行时配置
seed/                     工单开始时的种子快照
project/                  完成的消费者项目：交付的游戏（28 个文件）
baseline/                 直接 baseline：index.html、运行记录与最终回答
work-order/               归档的 0.3.6 工单：goal、analysis、solution、result、
                          review/verification 产物、运行时树和 tmp 证据
evaluation/               固定的 M2D-SES v1.1 标准、2D profile 和 score sheet；
                          v1.0 作为历史保留
tree/                     早期 0.3.3 树，仅为来源保留；0.3.6 树在 work-order/runtime/
media/                    受管结果与 baseline 的 960x600 截图
```

实时工单运行在本仓库之外的独立工作坊 Git 仓库中，`project/.xcoding` 是指向它的 junction。
归档的 `work-order/` 是该目录的副本，包含运行时和 `tmp/` 临时证据；实时工作坊不在本仓库中。

## 0.3.6 工单产出了什么

交付页面是 [`project/index.html`](project/index.html)，由本地 CSS、12 个 JavaScript 模块和
12 个测试文件支撑。它提供：

- 种子生成的地形：丘陵、地层、沙谷、洞穴、树木和安全出生点；
- 玩家重力、加速、AABB 碰撞、coyote time、jump buffer 和可变跳跃；
- 按住挖掘（裂纹阶段/粒子）与面向面的放置，带 reach、空格、玩家重叠和库存规则，以及拒绝反馈；
- 九格快捷栏，带每方块数量、数字键、滚轮切换和清晰的选中状态；
- 平滑、世界边界内 clamp 的相机；昼夜循环（太阳/月亮/星星、视差山丘、云、萤火虫、火把/玩家光照）；
- 本地 WebAudio 音效与持久静音；数字种子输入、暂停、坐标/深度 HUD、1280 宽度缩放、
  reduced-motion 支持和帮助面板；
- 版本化 `localStorage` 保存/恢复世界、玩家、数量、选择与设置，带防御性回退；
- 124 个自动化测试和绿色 page check。

在 `project/` 中复现验证：

```text
node --test "tests/**/*.test.js"    124 tests, 124 pass
python tools/page_check.py --window 960x600
                                    static/network checks pass; status marker green;
                                    202 colour buckets in the rendered canvas
```

下图是 [`media/xc-sandbox-0.3.6.png`](media/xc-sandbox-0.3.6.png)。它是种子 `20261030`、默认白天状态的干净
960x600 截图。页面是响应式的：其他窗口尺寸下 960x540 的舞台会缩放并留黑边，因此 HUD/游戏区看起来
会比这张裁剪图更大或更小。游戏还会恢复 `localStorage`；之前保存过的种子、时间或被编辑过的世界，
都会让普通浏览器打开时看起来不同。要复现截图：输入种子 `20261030` 并点 **Load**，或清除该页面的
站点数据，然后使用 960x600 视口。

## 直接 baseline 与 0.3.6 结果

Baseline 使用同一模型（`deepseek-flash`）、同一台机器和原始任务 prompt，关闭 workflow 直接运行
一次。启动配置和最终回答在 [`baseline/run.md`](baseline/run.md) 与
[`baseline/dsh-run.txt`](baseline/dsh-run.txt)。

| 直接 baseline | XC 0.3.6 标准 create 工单 |
| --- | --- |
| <img src="media/baseline-sandbox.png" alt="直接 baseline 沙盒截图" width="440"> | <img src="media/xc-sandbox-0.3.6.png" alt="XC 0.3.6 沙盒截图" width="440"> |

| 事实 | 直接 baseline | XC 0.3.6 工单 |
| --- | --- | --- |
| 交付布局 | 1 个文件 | 28 个文件（页面、CSS、12 模块、12 测试、工具、README） |
| 服务页面字节 | 98,883 | 170,377 |
| 项目总字节 | 98,883 | 185,102 |
| 提交的逻辑测试 | 0 | **124，全部通过** |
| 自动化 page check | 无 | 绿色 marker，202 个 canvas 色桶 |
| 服务文件外部引用 | 0 | 0 |
| 持久过程记录 | 无 | 完整标准工单 + 运行时树 |
| 独立视觉评审 | 无 | 通过；无必修 finding |

0.3.6 是比 one-shot baseline 大得多、测试充分得多的产品。按 v1.0 的工程加权公式它是最高分；按
v1.1 的 experience-first 标准它是**第四**，因为没有封闭的世界底线，地下方块挖掉后会露出天空。
one-shot baseline 不是体验最差的：它有封闭 bedrock/世界底线和地下背景，虽然无测试/音频，PES 仍
高于 0.3.6。

| 产物 | PES | ECS | Composite | Gate | High / medium |
| --- | ---: | ---: | ---: | --- | ---: |
| 0.3.3 pre-correction | 70.4 | 74.0 | **71.3** | pass | 0 / 4 |
| E3 / Verdant Hollow（参考） | **71.2** | 65.5 | 69.8 | pass | 0 / 3 |
| 0.3.3 standard | 57.6 | 81.0 | 63.5 | pass | **1 / 2** |
| **0.3.6 standard** | 50.0（capped） | **92.5** | **60.6** | pass | **2 / 2** |
| one-shot baseline | 55.8 | 38.0 | 51.4 | pass | 0 / 3 |

v1.1 分别报告 PES（composite 的 75%）、ECS（25%）和 capped composite。0.3.6 的 ECS 最高
（92.5：124 tests、12 modules、强持久化/无障碍），但两个 high defect 把 PES cap 到 50：没有
bedrock/世界底线，地下镂空露出天空。0.3.3 standard 也有一个 high defect（没有 bedrock），
PES cap 后 57.6。pre-correction 是 composite 第一；E3 是纯 PES 第一；两者在 rubric 分辨率内
（体验上并列）。v1.0 的 base/core/coverage 表是历史记录，不能与 v1.1 直接比较。

0.3.4 和 0.3.5 **没有按 v1.1 重评**：完整 artifact 已不再保留，只保留 v1.0 历史分数
（55/61/47 和 55/62/47）；不会从截图伪造 v1.1 分数。

E3 / Verdant Hollow 是 2026-10-28 消融实验的条件 E3（盲评字母 F），现已作为未来 sample 对比的
**固定参考条件**，不是标准 sample，也不是发布门槛。它拥有参考集中最丰富的核心沙盒世界（四个
biomes、ores、bedrock、14 种方块、minimap、day/night、audio），但没有 counted inventory、只有
17 tests、没有 pause/reduced motion。未来运行用它作为世界/表现和 core-demo 的参考。

## 回归历史

| 版本 / 运行 | 运行形态 | 服务字节 | 总字节 | 测试 | 色桶 | 备注 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 0.3.2 sample (C1) | full，无质量契约 | 38.1 KB | 69,140 | 28 | 53 | 历史；低于 baseline |
| 0.3.3 pre-correction | create-minimal（跳过阶段） | 132,680 | 168,758 | 34 | 285 | 被取代的特例；不是标准对比 |
| 0.3.3 standard | full lifecycle + 质量契约 | 111,090 | 141,977 | 33 | 292 | 历史 |
| 0.3.6 standard | full lifecycle + scope/signature/preservation 契约 | 170,377 | 185,102 | **124** | 202 | 当前标准 sample；v1.1 体验第 4 |

与被取代的特例存在 run-to-run 差异是预期的：特例跳过 analysis/solution，标准运行保留正常
生命周期。0.3.6 恢复了 0.3.5 丢失的 counts/tests/accessibility/responsiveness，并提升 base/core；
完整逐版本理由保留在项目评测历史中。

## 阅读工单

0.3.6 运行时树是 [`work-order/runtime/minecraft-sandbox.svg`](work-order/runtime/minecraft-sandbox.svg)
（可缩放），受管 XML 在 [`work-order/runtime/orchestration.xml`](work-order/runtime/orchestration.xml)。
它报告 `status=complete`、SHA-256 完整性有效、45 个 succeeded 节点、16 个 skipped 条件节点。

工单文档是 [`goal.md`](work-order/goal.md)、[`analysis.md`](work-order/analysis.md)、
[`solution.md`](work-order/solution.md) 和 [`result.md`](work-order/result.md)。评审和验证证据在
[`work-order/artifacts/`](work-order/artifacts/)。[`tree/`](tree/) 是 0.3.3 的旧树，仅为来源保留。

## 评测标准

每次 sample 运行都用固定的 [M2D-SES v1.1](evaluation/STANDARD.md) 评分：experience-first 的
**PES**（composite 75%）、灵活的 **Engineering & Code Quality Score (ECS)**（25%）、一个很小的
minimum gate（boot/offline、无致命错误、保存恢复），以及带等级的 defect ledger。
[2D sandbox profile](evaluation/PROFILE-2D-SANDBOX.md) 定义预期 journey 和完整性要求；
[score sheet](evaluation/SCORE-SHEET.md) 记录 PES/ECS/composite 与 defect caps。

v1.0 的 86 条细则和分数保留在 [`STANDARD-v1.0.md`](evaluation/STANDARD-v1.0.md) 和
[`SCORE-SHEET-v1.0.md`](evaluation/SCORE-SHEET-v1.0.md) 作为来源记录；v1.0 与 v1.1 分数不能直接
比较。标准只通过有意的版本化修订变更；已完成的 score sheet 不会被覆盖。

## 复现

前置条件：Python 3.12、Node.js 24、Google Chrome、Git，以及为宿主安装的 `xcoding` 包和 XC
Skills。从仓库根目录：

```powershell
$Checkout = (Get-Location).Path
$Sample = Join-Path $Checkout "samples/minecraft-sandbox-work-order"
$Workshop = Join-Path (Split-Path $Checkout -Parent) "minecraft-sandbox-workshop"

# 用干净 seed 替换已完成的 project。
if (Test-Path "$Sample/project/.xcoding") { [System.IO.Directory]::Delete("$Sample/project/.xcoding", $false) }
Remove-Item "$Sample/project" -Recurse -Force
New-Item -ItemType Directory -Force "$Sample/project" | Out-Null
Copy-Item "$Sample/seed/*" "$Sample/project/" -Recurse -Force

New-Item -ItemType Directory -Force (Join-Path $Workshop ".xcoding") | Out-Null
git -C $Workshop init
Copy-Item "$Sample/setup/WORKFLOW.md" (Join-Path $Workshop ".xcoding/WORKFLOW.md")
Copy-Item "$Sample/setup/xc-orchestration-runtime.json" (Join-Path $Workshop ".xcoding/xc-orchestration-runtime.json")
New-Item -ItemType Junction -Path (Join-Path $Sample "project/.xcoding") -Target (Join-Path $Workshop ".xcoding")

$env:DEEPSEEK_API_KEY = "<the key from the harness credential store>"
$env:DSH_PERMISSION_MODE = "danger-full-access"
Get-Content $Sample/prompt.md -Raw | dsh headless -
```

回归运行时，把 seed、Skills 和 `.agents` 镜像复制到不含公开 sample、baseline 或 prior result 的
独立工作区，在那里运行。prompt 的隔离规则禁止读取这些路径。

运行完成后，工单在 `$Workshop/.xcoding/work-orders/<work-order-id>/`。渲染其树：

```powershell
$Tree = "$Workshop/.xcoding/work-orders/<work-order-id>/runtime/orchestration.xml"
$viewer = xcoding viewer --tree $Tree --no-browser | ConvertFrom-Json
$svg = Invoke-WebRequest "$($viewer.url)api/trees/$($viewer.trees[0].tree_id)/svg"
[IO.File]::WriteAllBytes("orchestration-tree.svg", [Text.Encoding]::UTF8.GetBytes($svg.Content))
```

归档的 `work-order/` 是原始工作坊目录的副本，行尾统一为 LF；因此包含原始运行的绝对路径。

## 局限

- 这是单次示例运行，记录一次执行，不是 benchmark。
- `seed/` 是起始快照的重建，不是原始运行的逐字节恢复；完成的 `project/` 与归档工单是原始产物。
- 基线 prompt 与受管 prompt 按设计不同；受管运行还要满足测试、文档、验证、质量契约和隔离规则。
- 没有进行人类试玩；检查是自动化加截图审视。
- page-check 工具是示例消费者项目的一部分，不是通用 XC 能力。
- 工作流契约在 [`docs/`](../../docs/zh-CN/index.md)；本示例只展示它们，不定义或扩展它们。
