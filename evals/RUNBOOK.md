# Weibo CLI Eval Runbook

这份 runbook 用于跑第一轮 `with_skill` / `without_skill` 对照评估。

## 目标

验证 `weibo-cli` skill 在以下方面是否真的优于无 skill 基线：

- 更稳定地触发正确能力
- 更稳定地选对命令
- 更少漏掉前置条件
- 更少虚构不存在的功能

## 建议目录

可直接参考 `workspace-template/iteration-1/`。

建议每个 case 都记录：

- `outputs/response.md`：代理原始输出
- `timing.json`：耗时与 token
- `grading.json`：断言打分结果

整轮再记录：

- `benchmark.json`
- `feedback.json`

## 每个 case 怎么跑

每个用例各跑两次：

1. `with_skill`
2. `without_skill`

如果你后面在优化 skill 新版本，把 `without_skill` 改成 `old_skill` 更有意义。

## with_skill 指令模板

```text
执行这个任务。

- Skill path: <repo-root>
- Task: <把 evals.json 中的 prompt 原文贴进来>
- Save outputs to: <workspace>/<case>/with_skill/outputs/

要求：
- 在干净上下文中运行
- 把最终回答原文保存到 outputs/response.md
- 记录总 token 和 duration_ms 到 timing.json
```

## without_skill 指令模板

```text
执行这个任务。

- Task: <把 evals.json 中的 prompt 原文贴进来>
- Save outputs to: <workspace>/<case>/without_skill/outputs/

要求：
- 不提供任何 skill
- 在干净上下文中运行
- 把最终回答原文保存到 outputs/response.md
- 记录总 token 和 duration_ms 到 timing.json
```

## grading 原则

打分时只看 output 和 assertions，不脑补。

- 有明确证据才算 PASS
- 没提到就算 FAIL
- 模糊提到但不足以执行，也应判 FAIL

证据必须引用输出中的具体内容，而不是只写主观印象。

## benchmark 怎么看

重点先看这三个量：

- assertion pass rate
- 平均耗时
- 平均 token

如果 `with_skill` 比基线高很多 pass rate，且时间/token 增幅可接受，说明 skill 有实际价值。

## 什么时候进入下一轮

出现以下任一情况，就值得改 skill：

- 某些断言 `with_skill` 仍经常失败
- human feedback 持续指出说明顺序混乱
- 代理经常没触发 skill 或触发了错误命令
- 某些规则写得太多，导致输出变啰嗦或僵硬

下一轮时，把失败断言、反馈和执行记录一起对照 `SKILL.md` 修改，而不是凭印象补规则。