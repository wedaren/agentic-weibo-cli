---
name: agentic-weibo-cli
description: 使用内置的微博 CLI 处理扫码登录、发布微博、查看微博详情、查看个人微博列表、查询评论与转发、发表评论、点赞、取消点赞、删除自己发布的微博；还支持查看任意用户主页信息、关注列表、粉丝列表、搜索微博（含在关注用户中搜索）。用户提到微博登录、发微博、看微博、评论、点赞、删微博、查关注、查粉丝、查用户信息、确认发帖结果、搜索微博时，应使用此 skill。
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
- 查询私信、收藏等当前 CLI 还不支持的能力
- 批量多账号管理

说明：如果用户要“整理成 Markdown”，通常做法是先用本 skill 拉取微博数据，再由 agent 把结果整理成 Markdown 文本；这不需要 CLI 额外提供 `export` 子命令。

## 调用入口

始终优先使用当前 skill 目录下的脚本入口：

```bash
scripts/weibo-cli <subcommand> [...args]
```

不要假设当前工作目录是仓库根目录。包装脚本会优先使用 skill 根目录下的 `.venv`；若本地虚拟环境不存在或依赖不完整，会尝试按 `requirements.txt` 自动初始化运行环境。

`login` 默认是非交互的，适合 agent 直接调用。只有显式传入 `--prompt` 时，才会要求用户在终端粘贴 cookie。

如果任务需要把 CLI 结果继续交给脚本、评估器或其他 agent 处理，优先追加 `--json` 获取稳定机器可读输出。

## 命令选择

- 登录或刷新登录态：`scripts/weibo-cli login`
- 查看当前登录态是否可直接使用：`scripts/weibo-cli status`
- 查看当前登录态的机器可读结果：`scripts/weibo-cli status --json`
- 检查浏览器依赖：`scripts/weibo-cli login --check-browser`
- 使用环境变量写入登录态：`scripts/weibo-cli login --from-env`
- 仅在明确需要人工粘贴 cookie 时：`scripts/weibo-cli login --prompt`
- 已有本地登录态但要强制刷新时：`scripts/weibo-cli login --force`
- 发布微博：`scripts/weibo-cli post --text "你的微博正文"`
- 查看微博详情：`scripts/weibo-cli show --weibo-id <id>`
- 查看最近微博：`scripts/weibo-cli list --limit 10 --page 1`
- 查看任意用户最近微博：`scripts/weibo-cli list --uid <UID> --limit 20`
- 查看最近转发微博：`scripts/weibo-cli list --limit 20 --only-reposts`
- 查看最近原创微博：`scripts/weibo-cli list --limit 20 --only-originals`
- 查看评论：`scripts/weibo-cli comments --weibo-id <id> --limit 20 --page 1`
- 发表评论：`scripts/weibo-cli comment --weibo-id <id> --text "你的评论正文"`
- 点赞微博：`scripts/weibo-cli like --weibo-id <id>`
- 取消点赞：`scripts/weibo-cli unlike --weibo-id <id>`
- 删除自己发布的微博：`scripts/weibo-cli delete --weibo-id <id>`
- 查询转发：`scripts/weibo-cli reposts --weibo-id <id> --limit 20 --page 1`
- 查看任意用户信息：`scripts/weibo-cli user --uid <UID>`
- 查看当前账号关注列表（全量，agent 推荐）：`scripts/weibo-cli following --all-pages --json`
- 查看当前账号关注列表（单页）：`scripts/weibo-cli following`
- 查看指定用户关注列表（全量）：`scripts/weibo-cli following --uid <UID> --all-pages --json`
- 查看指定用户关注列表（单页）：`scripts/weibo-cli following --uid <UID> --page 1`
- 查看当前账号粉丝列表（全量，agent 推荐）：`scripts/weibo-cli followers --all-pages --json`
- 查看当前账号粉丝列表（单页）：`scripts/weibo-cli followers`
- 查看指定用户粉丝列表（全量）：`scripts/weibo-cli followers --uid <UID> --all-pages --json`
- 查看指定用户粉丝列表（单页）：`scripts/weibo-cli followers --uid <UID> --page 2`
- 全网搜索微博：`scripts/weibo-cli search --keyword <关键词>`
- 仅在关注用户中搜索微博：`scripts/weibo-cli search --keyword <关键词> --following-only`
- 同步关注时间线到本地数据库：`scripts/weibo-cli sync`
- 在本地数据库中搜索：`scripts/weibo-cli local search --keyword <关键词>`
- 列出本地缓存帖子：`scripts/weibo-cli local list`
- 本地数据库统计：`scripts/weibo-cli local stats`

说明：面向最终用户的对话回复默认仍优先使用文本格式；只有在需要稳定字段时才切到 `--json`。

说明：`user`、`following`、`followers` 结果来自本地 TTL 缓存（用户信息 10 分钟、列表 5 分钟），重复查询同一对象不会重复发起网络请求。如需强制刷新，可在命令前加 `WEIBO_CACHE_DISABLED=1`。

说明：`following --all-pages` / `followers --all-pages` 一次性自动翻页拉取全量列表，JSON 输出含 `total` 和 `has_more=false`；单页模式的 JSON 输出含 `has_more`，`true` 表示还有更多页。

更完整的参数示例见 [references/commands.md](references/commands.md)。

## 执行规则

1. 用户未确认最终文本时，不要执行 `post`。
2. 缺少 `weibo-id` 时，不要执行 `reposts`，先向用户索取明确 ID。
3. 缺少 `weibo-id` 时，不要执行 `show`、`comments`、`comment`、`like`、`unlike`、`delete`，先向用户索取明确 ID。
4. 默认先用 `status` 检查登录态；只有缺失或失效时，再执行 `login`。命令因鉴权失败退出（`--json` 模式下 `error.category == “auth”` 且 `error.next_action == “login”`）时，执行 `login`（**不要** `login --force`）后立即重试原命令。
5. 对查看、读取、列举这类非破坏性任务，如果登录态失效，应直接继续执行 `login` 并在登录成功后回到原任务，不要额外停下来征求一次”是否现在执行”的确认。
6. 本地登录态仍有效时，不要重复执行 `login`；如确需刷新，显式使用 `login --force`。
7. 删除微博前必须确认用户已经明确要求删除，且目标微博 ID 无歧义。
8. 用户如果说“最近转发的微博”“我转发过什么”，优先使用 `list --only-reposts`，不要先列全量再手工筛选。
9. 对发布、评论、点赞、取消点赞、删除这类会改变微博状态的操作，执行前必须先向用户确认具体动作和目标对象。
10. 如果任务需要验证发布或评论结果，执行后再读一次 `show`、`comments` 或 `list` 做结果确认。
11. 查询关注/粉丝列表时，若用户没有指定 UID，默认查询当前登录账号（`following` / `followers` 不传 `--uid` 即可）。
12. `user`、`following`、`followers` 结果有缓存；若用户明确要求"最新数据"或"刷新"，在命令前加 `WEIBO_CACHE_DISABLED=1`。
13. 需要获取完整关注/粉丝列表时（统计总数、全量与其他数据联动），使用 `--all-pages` 而不是手动循环翻页；JSON 的 `has_more=false` 表示已是全量。
14. `search --following-only` 会在全网结果中过滤关注用户，自动翻页最多 5 页；若返回条数少于 `--limit`，说明关注用户在该关键词下发帖本来就少，属正常。
15. `sync` 每次拉取首页时间线 N 页（默认 3 页，约 60 条），写入 `~/.local/share/weibo-cli/feed.db`，重复帖子自动跳过；`local search` 在本地库中做 LIKE 搜索，**无需联网**，适合离线分析关注用户的历史内容。
16. 如用户想分析关注用户近期内容，应先确认本地库是否已同步（`local stats`），若总条数很少则先执行 `sync --pages 5` 初始化。
17. 查看某个用户最近发布的微博，使用 `list --uid <UID>`；`list` 不传 `--uid` 则只查当前登录账号自己的微博。**不要**尝试 `search --keyword "from:<UID>"`，该语法不受支持。
18. 用户明确说"我关注的用户里"、"关注的人发了"、"关注用户中"等语境时，**必须**使用 `search --keyword <关键词> --following-only`，不要用无过滤的全网搜索；若本地库已有数据（`local stats` 总条数 > 0），也可优先用 `local search --keyword <关键词>` 避免联网。
19. 搜索非中文关键词（尤其是人名）时，若返回 0 结果，在报告"无结果"前**必须**主动尝试 1–2 个最可能的正确拼写并重新执行搜索；不要等用户手动纠正后才重试。例：用户输入 "kaaparthy" / "karparthy" → 应自动尝试 "karpathy"。
20. 用户用简短词（"好的"、"是"、"行"、"ok"、"嗯"）回复上一轮提出的操作建议时，直接执行其中**最有价值**的那个操作，不要再次列出选项或征求选择。
## 完成前检查

- `status` 成功时，应看到“已配置 / 可直接使用 / 来源 / UID / 更新时间”等状态信息。
- `login` 成功时，终端应出现“登录态已写入”并输出 UID。
- `post` 成功时，终端应出现“发布成功”并返回微博 ID。
- `show` 成功时，应看到微博 ID、正文、作者和互动计数。
- `list` 成功时，输出应包含微博 ID 和正文；若是转发微博，还应看到原微博内容；`list --uid <UID>` 可查看任意用户的最近微博。
- `comments` 成功时，输出应包含评论用户、时间和正文；若无结果，应明确说明没有可返回的评论记录。
- `comment` 成功时，终端应出现“评论成功”并返回评论 ID。
- `like` / `unlike` / `delete` 成功时，应返回目标微博 ID 和操作结果说明。
- `reposts` 成功时，输出应包含转发用户、时间、来源和正文；若无结果，应明确说明没有可返回的转发记录。
- `user` 成功时，应看到昵称、UID、粉丝数、关注数、微博数，以及简介、认证信息（如有）。
- `following` / `followers` 成功时，应看到带编号的用户列表（昵称、UID、粉丝数等）；`--all-pages` 时还应看到合计条数；若 `items` 为空列表（exit 0），告知用户"未能获取到关注/粉丝列表，该功能可能处于不可用状态"，并报告给开发者。
- `search` 成功时，应看到带编号的微博列表（微博 ID、作者、互动计数、正文）；若无结果，应明确说明未找到相关微博。
- `sync` 成功时，应看到新增条数、跳过条数、过期清理条数、数据库总计及路径。
- `local search` / `local list` 成功时，应看到带编号的微博列表（含"同步"时间戳）；若无结果，应说明本地数据库中未找到相关内容。
- `local stats` 成功时，应看到总条数、覆盖用户数、最早/最新同步时间、保留天数及路径。

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