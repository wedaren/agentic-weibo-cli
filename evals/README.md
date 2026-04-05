# Weibo CLI Evals

这个目录用于按 agentskills 的评估方法验证 `agentic-weibo-cli` 的输出质量，而不是评估微博平台本身。

## 评估目标

当前评估先只覆盖无副作用场景，确认 skill 是否能稳定做到：

- 被正确触发
- 选对命令
- 提醒必要前置条件
- 不编造不存在的能力

当前第一轮测试用例定义在 `evals.json`，只包含：

- 登录引导
- 查看最近微博
- 查询指定微博转发

## 与 agentskills 规范对齐的约定

这个仓库采用以下评估约定：

- 手写维护的核心文件是 `evals/evals.json`
- 每个测试用例至少包含 `prompt` 和 `expected_output`
- `assertions` 保持可验证、不过度依赖固定措辞
- 每轮完整评估放到独立的 `iteration-N/` 目录
- 每个测试用例使用独立目录 `eval-<slug>/`
- 每个用例都跑 `with_skill` 和 `without_skill` 两个配置；优化已有 skill 时，优先改成 `old_skill`
- 每次运行都记录 `outputs/`、`timing.json`、`grading.json`
- 每轮汇总记录 `benchmark.json` 和 `feedback.json`

## 为什么先不测真实发微博

真实 `post` 会产生副作用，不适合高频自动评估。

建议把评估分成三层：

1. 命令选择与说明是否正确
2. 是否能正确调用无副作用命令或 `--help`
3. 在人工确认下做少量真实链路验证

## 推荐工作区结构

按照 agentskills 规范，评估结果应放在 skill 目录旁边的独立 workspace 中，例如：

```text
agentic-weibo-cli/
├── SKILL.md
└── evals/
    ├── evals.json
    ├── README.md
    └── RUNBOOK.md

agentic-weibo-cli-workspace/
└── iteration-1/
    ├── eval-login-guidance/
    │   ├── with_skill/
    │   │   ├── outputs/
    │   │   ├── timing.json
    │   │   └── grading.json
    │   └── without_skill/
    │       ├── outputs/
    │       ├── timing.json
    │       └── grading.json
    ├── eval-list-recent-weibos/
    ├── eval-inspect-reposts/
    ├── benchmark.json
    └── feedback.json
```

## 当前 assertions 策略

agentskills 建议先有 prompt 和 expected output，再根据第一轮输出补充 assertions。这个仓库当前已经带了第一版 assertions，但仍保持中等粒度，目标是验证：

- skill 是否被正确触发
- 子命令是否选择正确
- 前置条件是否被正确提醒
- 是否出现不支持能力的幻觉

这些断言故意避免逐字匹配某一句固定文案，减少脆弱性。

## 后续如何调整 assertions

在你看过真实输出后，再继续收紧或替换断言。断言应尽量客观、可验证、不过度依赖固定措辞。

好的例子：

- 输出明确使用 `reposts` 子命令
- 输出包含 `--weibo-id`
- 输出提醒先登录或确认登录态
- 输出没有误导用户使用不存在的评论查询能力

不好的例子：

- 输出很好
- 输出必须逐字包含某一句完整文案

## 人工复核建议

断言通过不代表输出一定好用。每轮评估后，人工至少回答这几个问题：

- 这个回答像不像真正能拿给用户直接执行的指导？
- 信息顺序是否清楚？
- 有没有多余限制或没必要的废话？
- 有没有 technically correct 但实际不方便执行的地方？

把这些意见记录到该轮 workspace 的 `feedback.json` 中，再进入下一轮 skill 修改。

## 下一步

直接参考 `RUNBOOK.md` 跑完整评估循环。runbook 已按 agentskills 的术语和产物命名整理为：

- 评估前准备
- `with_skill` / `without_skill` 或 `old_skill` 对照运行
- `timing.json` / `grading.json` / `benchmark.json` / `feedback.json` 记录方式
- 进入下一轮 skill 修改的判断标准