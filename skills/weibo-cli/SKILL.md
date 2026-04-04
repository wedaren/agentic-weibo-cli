---
name: weibo-cli
description: 使用内置的微博 CLI 处理扫码登录、发布微博、查看个人微博列表、查询指定微博转发。用户提到微博登录、发微博、查看最近微博、确认发帖结果、查询某条微博转发时，应使用此 skill。
compatibility: 需要 Python 3.14+。首次使用前建议创建 skills/weibo-cli/.venv 并安装 requirements.txt。登录流程需要本地 Chrome 或 Chromium，并可访问 passport.weibo.com、weibo.com、m.weibo.cn。执行命令时优先从当前 skill 根目录调用 scripts/weibo-cli。
license: Proprietary
metadata:
  owner: agentic-weibo-cli
  entrypoint: scripts/weibo-cli
---

# Weibo CLI

## 何时使用

- 用户要登录微博或刷新本地登录态
- 用户要发布一条纯文本微博
- 用户要查看当前账号最近微博
- 用户要查询某条微博的转发列表

## 不要用于

- 用户只是想润色微博文案，但还没确认要发布
- 查询评论、点赞、粉丝、私信等当前 CLI 不支持的能力
- 批量多账号管理

## 调用入口

始终优先使用当前 skill 目录下的脚本入口：

```bash
scripts/weibo-cli <subcommand> [...args]
```

不要假设当前工作目录是仓库根目录。若 `skills/weibo-cli/.venv/` 存在，包装脚本会优先使用其中的 Python 解释器。

## 命令选择

- 登录或刷新登录态：`scripts/weibo-cli login`
- 检查浏览器依赖：`scripts/weibo-cli login --check-browser`
- 使用环境变量写入登录态：`scripts/weibo-cli login --from-env`
- 发布微博：`scripts/weibo-cli post --text "你的微博正文"`
- 查看最近微博：`scripts/weibo-cli list --limit 10 --page 1`
- 查询转发：`scripts/weibo-cli reposts --weibo-id <id> --limit 20 --page 1`

更完整的参数示例见 [references/commands.md](references/commands.md)。

## 执行规则

1. 用户未确认最终文本时，不要执行 `post`。
2. 缺少 `weibo-id` 时，不要执行 `reposts`，先向用户索取明确 ID。
3. 如怀疑登录态失效，优先执行 `login` 或让用户确认是否重登。
4. 如果任务需要验证发布结果，发布后再执行一次 `list --limit 5 --page 1`。

## 完成前检查

- `login` 成功时，终端应出现“登录态已写入”并输出 UID。
- `post` 成功时，终端应出现“发布成功”并返回微博 ID。
- `list` 成功时，输出应包含微博 ID 和正文；若是转发微博，还应看到原微博内容。
- `reposts` 成功时，输出应包含转发用户、时间、来源和正文；若无结果，应明确说明没有可返回的转发记录。

## 已验证事实

- 2026-04-04 已完成一轮真实端到端验证：浏览器扫码登录、真实发微博、读取最近微博、查询转发空结果均成功。
- `login --from-env` 也已在真实登录态上验证通过，可把环境变量中的 cookie/uid 回写到本地文件。
- 当前仓库还提供无副作用自检脚本 `scripts/self-check`，可快速验证 skills、CLI 帮助、浏览器自动化和最近微博读取能力。

## 常见陷阱

- `scripts/weibo-cli` 依赖 Python 运行环境；如果命令无法执行，先确认 `python3` 可用，或先初始化 `skills/weibo-cli/.venv/`。
- 登录失败通常优先排查浏览器自动化、网络可达性和 cookie 有效性，不要直接归因为 CLI 本身错误。
- `list` 和 `reposts` 的空结果不总是失败，先区分“当前页无数据”和“鉴权/接口错误”。