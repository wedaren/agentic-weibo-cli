# Weibo CLI Evals

这个目录用于评估 `weibo-cli` skill 的输出质量，而不是评估微博平台本身。

## 第一轮目标

先只覆盖无副作用场景，确认 skill 是否能稳定做到：

- 被正确触发
- 选对命令
- 提醒必要前置条件
- 不编造不存在的能力

当前第一轮测试用例定义在 `evals.json`，只包含：

- 登录引导
- 查看最近微博
- 查询指定微博转发

## 为什么先不测真实发微博

真实 `post` 会产生副作用，不适合高频自动评估。

建议把评估分成三层：

1. 命令选择与说明是否正确
2. 是否能正确调用无副作用命令或 `--help`
3. 在人工确认下做少量真实链路验证

## 推荐工作区结构

建议把每一轮评估结果放在单独目录中，例如：

```text
weibo-cli/
├── SKILL.md
└── evals/
    ├── evals.json
    └── README.md

weibo-cli-workspace/
└── iteration-1/
    ├── login-guidance/
    │   ├── with_skill/
    │   │   ├── outputs/
    │   │   ├── timing.json
    │   │   └── grading.json
    │   └── without_skill/
    │       ├── outputs/
    │       ├── timing.json
    │       └── grading.json
    ├── list-recent-weibos/
    ├── inspect-reposts/
    └── benchmark.json
```

## 第一轮怎么跑

每个用例至少跑两次：

1. `with_skill`：把当前仓库根目录作为 skill 提供给代理
2. `without_skill`：不给 skill，用同一个 prompt 再跑一次

如果你是在优化 skill 新版本，更好的对照组是旧版本 skill 快照，而不是完全不带 skill。

## 第一轮先看什么

第一轮不要急着写很细的断言，先看真实输出长什么样。

重点看这四件事：

- 是否明确提到 `weibo-cli`
- 是否选择了正确子命令
- 是否提醒了登录或参数前置条件
- 是否把不支持的能力说成已支持

## 当前 assertions 策略

当前 `evals.json` 已包含第一版 assertions，目标是验证：

- skill 是否被正确触发
- 子命令是否选择正确
- 前置条件是否被正确提醒
- 是否出现不支持能力的幻觉

这些断言故意保持中等粒度，避免过度依赖某一句固定措辞。

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

把这些意见记录到每轮 workspace 的 `feedback.json` 中，再进入下一轮 skill 修改。

## 可直接照抄的第一轮 runbook

直接参考 `RUNBOOK.md`。其中包含：

- 如何准备 `with_skill` / `without_skill` 目录
- 每个 case 怎么记录输出
- `grading.json` / `benchmark.json` / `feedback.json` 的写法
- 什么时候进入下一轮 skill 修改