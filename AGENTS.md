# agentic-weibo-cli

## 一句话介绍

面向个人账号的微博命令行工具，提供 CLI 命令与配套 skills 文档，支持扫码登录、发微博、列微博、查转发。

## CLI 与 Skills

```bash
# 查看 CLI 帮助
npm run help

# 列出 skills
npm run cli -- skills

# 查看某个 skill 文档
npm run cli -- skills show weibo-cli

# 初始化 Python 虚拟环境
npm run skills:venv
```

`skills/` 目录里的 `SKILL.md` 用于给 AI 代理和团队成员提供稳定操作说明；CLI 用于真正执行微博动作。

## Skills 约定

- `skills/` 是当前仓库的 skill 源目录
- 每个 skill 目录必须包含 `SKILL.md`，并使用 YAML frontmatter 声明 `name`、`description`
- 代理应先根据 `description` 判断是否需要加载 skill，再阅读 `SKILL.md` 正文执行步骤
- 运行 `npm run cli -- skills prompt` 可输出 `<available_skills>` XML，供 agent 宿主注入上下文
- 运行 `npm run cli -- skills validate` 可校验 skill 是否符合目录与 frontmatter 规范
- 当前仓库收敛为单一 `weibo-cli` skill，skill 通过 `skills/weibo-cli/scripts/weibo-cli` 调用 skill 目录中的 Python 实现
- 所有 CLI 业务实现均位于 `skills/weibo-cli/scripts/weibo_cli/`
- `skills/weibo-cli/.venv/` 是 skill 本地虚拟环境，用于安装 `requests` 与 `playwright`
- 包装脚本会优先使用 `skills/weibo-cli/.venv/bin/python3`，否则回退到系统 `python3`

## 启动

```bash
# MVP 阶段（首次运行）
bash tick.sh

# 进化阶段（MVP 完成后）
bash evolve.sh
```

## 你只需要做的事

1. 编辑 `.agent/program.md` — 写目标和约束
2. 运行 `bash tick.sh` — 系统自动完成 MVP
3. 追加功能 — 在 `program.md` 末尾加 `- [ ] 你的想法`
4. 运行 `bash evolve.sh` — 系统自动实现新功能

## 需要你介入的唯一情况

```bash
cat .agent/inbox/needs-you.md   # 查看问题
# 处理完后
rm .agent/inbox/needs-you.md
bash tick.sh  # 或 evolve.sh
```

## 查看进度

```bash
cat .agent/tasks.json | python3 -m json.tool   # 任务状态
cat .agent/decisions.md                         # PM 的决策
ls .agent/experiments/                          # 迭代历史
ls .agent/knowledge/                            # 知识积累
```

## 目录结构

```
.agent/
  program.md       唯一需求基准（你来写）
  tasks.json       任务队列（系统维护）
  state.json       全局状态（系统维护）
  decisions.md     PM 决策日志
  knowledge/       research 知识库
  experiments/     迭代历史
  inbox/           需要你介入时才有文件

.github/
  agents/
    pm.agent.md      PM Agent prompt
    coder.agent.md   Coder Agent prompt
    validator.agent.md
    research.agent.md
    evolution.agent.md
  prompts/
    *.prompt.md      Chat 可调用提示词
  instructions/
    *.instructions.md 仓库指令文件

skills/
  weibo-cli/
    SKILL.md       微博 CLI 总 skill
    .venv/         skill 本地虚拟环境（初始化后生成）
    requirements.txt Python 运行依赖
    scripts/
      weibo-cli    agent 调用入口
      weibo_cli/   Python 实现源码
    references/
      commands.md  子命令与参数说明

tick.sh            MVP 阶段调度器
evolve.sh          进化阶段调度器
```
