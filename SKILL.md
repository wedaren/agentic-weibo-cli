---
name: agentic-weibo-cli
description: 使用内置的微博 CLI 处理扫码登录、发布微博、查看微博详情、查看个人微博列表、查询评论与转发、发表评论、点赞、取消点赞、删除自己发布的微博。用户提到微博登录、发微博、看微博、评论、点赞、删微博、确认发帖结果时，应使用此 skill。
compatibility: 需要 Python 3.14+。首次使用前建议创建 .venv 并安装 requirements.txt。登录流程需要本地 Chrome 或 Chromium，并可访问 passport.weibo.com、weibo.com、m.weibo.cn。执行命令时优先从当前 skill 根目录调用 scripts/weibo-cli。
license: Proprietary
metadata:
  owner: agentic-weibo-cli
  entrypoint: scripts/weibo-cli
---

# Weibo CLI

## 何时使用

- 用户要登录微博或刷新本地登录态
- 用户要发布一条纯文本微博
- 用户要把最近微博、最近转发或某条微博详情整理成 Markdown 摘要
- 用户要查看某条微博详情或评论
- 用户要对某条微博发表评论
- 用户要给某条微博点赞或取消点赞
- 用户要删除自己刚发的微博
- 用户要查看当前账号最近微博
- 用户要查询某条微博的转发列表

## 不要用于

- 用户只是想润色微博文案，但还没确认要发布
- 查询粉丝、关注、私信、收藏等当前 CLI 还不支持的能力
- 批量多账号管理

说明：如果用户要“整理成 Markdown”，通常做法是先用本 skill 拉取微博数据，再由 agent 把结果整理成 Markdown 文本；这不需要 CLI 额外提供 `export` 子命令。

## 调用入口

始终优先使用当前 skill 目录下的脚本入口：

```bash
scripts/weibo-cli <subcommand> [...args]
```

不要假设当前工作目录是仓库根目录。包装脚本会优先使用 skill 根目录下的 `.venv`；若本地虚拟环境不存在或依赖不完整，会尝试按 `requirements.txt` 自动初始化运行环境。

`login` 默认是非交互的，适合 agent 直接调用。只有显式传入 `--prompt` 时，才会要求用户在终端粘贴 cookie。

## 命令选择

- 登录或刷新登录态：`scripts/weibo-cli login`
- 查看当前登录态是否可直接使用：`scripts/weibo-cli status`
- 检查浏览器依赖：`scripts/weibo-cli login --check-browser`
- 使用环境变量写入登录态：`scripts/weibo-cli login --from-env`
- 仅在明确需要人工粘贴 cookie 时：`scripts/weibo-cli login --prompt`
- 已有本地登录态但要强制刷新时：`scripts/weibo-cli login --force`
- 发布微博：`scripts/weibo-cli post --text "你的微博正文"`
- 查看微博详情：`scripts/weibo-cli show --weibo-id <id>`
- 查看最近微博：`scripts/weibo-cli list --limit 10 --page 1`
- 查看最近转发微博：`scripts/weibo-cli list --limit 20 --only-reposts`
- 查看最近原创微博：`scripts/weibo-cli list --limit 20 --only-originals`
- 查看评论：`scripts/weibo-cli comments --weibo-id <id> --limit 20 --page 1`
- 发表评论：`scripts/weibo-cli comment --weibo-id <id> --text "你的评论正文"`
- 点赞微博：`scripts/weibo-cli like --weibo-id <id>`
- 取消点赞：`scripts/weibo-cli unlike --weibo-id <id>`
- 删除自己发布的微博：`scripts/weibo-cli delete --weibo-id <id>`
- 查询转发：`scripts/weibo-cli reposts --weibo-id <id> --limit 20 --page 1`

更完整的参数示例见 [references/commands.md](references/commands.md)。

## 执行规则

1. 用户未确认最终文本时，不要执行 `post`。
2. 缺少 `weibo-id` 时，不要执行 `reposts`，先向用户索取明确 ID。
3. 缺少 `weibo-id` 时，不要执行 `show`、`comments`、`comment`、`like`、`unlike`、`delete`，先向用户索取明确 ID。
4. 默认先用 `status` 检查登录态；只有缺失或失效时，再执行 `login`。
5. 对查看、读取、列举这类非破坏性任务，如果登录态失效，应直接继续执行 `login` 并在登录成功后回到原任务，不要额外停下来征求一次“是否现在执行”的确认。
6. 本地登录态仍有效时，不要重复执行 `login`；如确需刷新，显式使用 `login --force`。
7. 删除微博前必须确认用户已经明确要求删除，且目标微博 ID 无歧义。
8. 用户如果说“最近转发的微博”“我转发过什么”，优先使用 `list --only-reposts`，不要先列全量再手工筛选。
9. 对发布、评论、点赞、取消点赞、删除这类会改变微博状态的操作，执行前必须先向用户确认具体动作和目标对象。
10. 如果任务需要验证发布或评论结果，执行后再读一次 `show`、`comments` 或 `list` 做结果确认。

## 完成前检查

- `status` 成功时，应看到“已配置 / 可直接使用 / 来源 / UID / 更新时间”等状态信息。
- `login` 成功时，终端应出现“登录态已写入”并输出 UID。
- `post` 成功时，终端应出现“发布成功”并返回微博 ID。
- `show` 成功时，应看到微博 ID、正文、作者和互动计数。
- `list` 成功时，输出应包含微博 ID 和正文；若是转发微博，还应看到原微博内容。
- `comments` 成功时，输出应包含评论用户、时间和正文；若无结果，应明确说明没有可返回的评论记录。
- `comment` 成功时，终端应出现“评论成功”并返回评论 ID。
- `like` / `unlike` / `delete` 成功时，应返回目标微博 ID 和操作结果说明。
- `reposts` 成功时，输出应包含转发用户、时间、来源和正文；若无结果，应明确说明没有可返回的转发记录。

## 已验证事实

- 2026-04-04 已完成一轮真实端到端验证：浏览器扫码登录、真实发微博、读取最近微博、查询转发空结果均成功。
- `login --from-env` 也已在真实登录态上验证通过，可把环境变量中的 cookie/uid 回写到本地文件。
- 当前仓库还提供无副作用自检脚本 `scripts/self-check`，可快速验证 skills、CLI 帮助、浏览器自动化和最近微博读取能力。

## 评估与迭代

- 当前 skill 的第一版评估用例位于 `evals/evals.json`。
- 建议优先评估无副作用场景：登录引导、查看最近微博、查询转发命令选择。
- 若要比较 skill 改动效果，始终在干净上下文中各跑一轮 `with_skill` 与 `without_skill`，或 `new_skill` 与 `old_skill`。
- 评估目录结构和人工复核建议见 `evals/README.md`。

## 常见陷阱

- `scripts/weibo-cli` 依赖 Python 运行环境；若 `.venv` 不存在，包装脚本会尝试自动创建并安装 `requirements.txt`。如果仍失败，先确认 `python3` 与网络可用。
- `login` 默认不会因为扫码失败而退回终端交互输入；如果确实要人工粘贴 cookie，必须显式传 `--prompt`。
- 若只是想确认当前是否已登录，先执行 `status`，不要直接重新跑 `login`。
- 登录失败通常优先排查浏览器自动化、网络可达性和 cookie 有效性，不要直接归因为 CLI 本身错误。
- `list` 和 `reposts` 的空结果不总是失败，先区分“当前页无数据”和“鉴权/接口错误”。