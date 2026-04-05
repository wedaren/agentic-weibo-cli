# Weibo CLI Eval Runbook

这份 runbook 按 agentskills 的评估循环整理，用于跑 `agentic-weibo-cli` 的 `with_skill` / `without_skill` 对照评估。

## 目标

验证 skill 在以下方面是否真的优于基线：

- 更稳定地触发正确能力
- 更稳定地选对命令
- 更少漏掉前置条件
- 更少虚构不存在的功能

## 评估前准备

1. 以 `evals/evals.json` 作为单一测试用例来源。
2. 在 skill 目录旁边创建独立 workspace，例如 `agentic-weibo-cli-workspace/`。
3. 为本轮创建 `iteration-N/` 目录。
4. 为每个测试用例创建 `eval-<slug>/` 目录。
5. 每个用例下准备 `with_skill/outputs/` 与 `without_skill/outputs/`。

如果你是在迭代已有 skill，新版本对照时更推荐：

1. 先快照旧版 skill。
2. 把基线目录从 `without_skill/` 改成 `old_skill/`。

直接生成第一轮目录骨架可运行：

```bash
npm run evals:init -- --workspace ../agentic-weibo-cli-workspace --iteration 1
```

如果要自动快照旧版 skill：

```bash
npm run evals:init -- --workspace ../agentic-weibo-cli-workspace --iteration 2 --baseline old_skill --snapshot-old-skill
```

这个脚本会自动生成：

- `iteration-N/benchmark.json`
- `iteration-N/feedback.json`
- 每个 `eval-<slug>/README.md`
- 每个配置目录下的 `task.md`
- `with_skill/outputs/` 与基线配置的 `outputs/`

## 建议目录

可直接参考 `workspace-template/iteration-1/`。

每个 case 建议记录：

- `outputs/response.md`：代理原始输出
- `timing.json`：耗时与 token
- `grading.json`：断言打分结果

整轮再记录：

- `benchmark.json`
- `feedback.json`

## 运行原则

- 每次 run 都必须在干净上下文中执行
- `with_skill` 和 `without_skill` 使用完全相同的 prompt
- 输出目录必须分开，避免互相污染
- timing 数据在 run 完成时立即落盘，避免丢失

## with_skill 指令模板

```text
执行这个任务。

- Skill path: <repo-root>
- Task: <把 evals.json 中的 prompt 原文贴进来>
- Save outputs to: <workspace>/iteration-<N>/eval-<slug>/with_skill/outputs/

要求：
- 在干净上下文中运行
- 把最终回答原文保存到 outputs/response.md
- 记录 total_tokens 和 duration_ms 到 with_skill/timing.json
```

## without_skill 指令模板

```text
执行这个任务。

- Task: <把 evals.json 中的 prompt 原文贴进来>
- Save outputs to: <workspace>/iteration-<N>/eval-<slug>/without_skill/outputs/

要求：
- 不提供任何 skill
- 在干净上下文中运行
- 把最终回答原文保存到 outputs/response.md
- 记录 total_tokens 和 duration_ms 到 without_skill/timing.json
```

## old_skill 指令模板

```text
执行这个任务。

- Skill path: <workspace>/skill-snapshot/
- Task: <把 evals.json 中的 prompt 原文贴进来>
- Save outputs to: <workspace>/iteration-<N>/eval-<slug>/old_skill/outputs/

要求：
- 使用旧版 skill 快照作为基线
- 在干净上下文中运行
- 把最终回答原文保存到 outputs/response.md
- 记录 total_tokens 和 duration_ms 到 old_skill/timing.json
```

## grading 原则

打分时只看 output 和 assertions，不脑补。

- 有明确证据才算 PASS
- 没提到就算 FAIL
- 模糊提到但不足以执行，也应判 FAIL
- 证据必须引用输出中的具体内容，而不是只写主观印象

如果某个 assertion 长期总是通过或总是失败，应在下一轮调整，而不是继续保留成无效信号。

## benchmark 怎么看

重点先看这三个量：

- assertion pass rate
- 平均耗时
- 平均 token

如果 `with_skill` 比基线高很多 pass rate，且时间或 token 增幅可接受，说明 skill 有实际价值。

单轮、少样本时不要过度解读 `stddev`；先看原始通过数和 delta。

## human feedback 怎么写

每个用例都做一次人工复核，并把具体反馈写入 `feedback.json`。

- 有明确问题就写可执行反馈
- 没发现问题就保留空字符串
- 避免写“感觉一般”这类不可操作描述

## 什么时候进入下一轮

出现以下任一情况，就值得改 skill：

- 某些断言在 `with_skill` 下仍经常失败
- human feedback 持续指出说明顺序混乱
- 代理经常没触发 skill 或触发了错误命令
- 某些规则写得太多，导致输出变啰嗦或僵硬

下一轮时，把失败断言、反馈和执行记录一起对照 `SKILL.md` 修改，而不是凭印象补规则。