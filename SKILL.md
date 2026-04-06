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
- 同步关注时间线到本地数据库：`scripts/weibo-cli sync`（默认 5 页 ≈ 100 条）
- 同步更多页以获取更广历史覆盖：`scripts/weibo-cli sync --pages 10`
- 逐用户全量同步（深度抓取，带随机延迟）：`scripts/weibo-cli sync --per-user`
- 逐用户同步（指定每人页数，跳过 12 小时内已同步用户）：`scripts/weibo-cli sync --per-user --pages-per-user 5 --skip-hours 12`
- 逐用户同步（强制重新同步所有用户）：`scripts/weibo-cli sync --per-user --force`
- 在本地数据库中搜索：`scripts/weibo-cli local search --keyword <关键词>`
- 在本地数据库中搜索（限最近 N 天）：`scripts/weibo-cli local search --keyword <关键词> --days 7`
- 在本地数据库中搜索（限定用户 UID）：`scripts/weibo-cli local search --keyword <关键词> --uid <UID>`
- 在本地数据库中搜索（限定用户昵称）：`scripts/weibo-cli local search --keyword <关键词> --user-name <昵称>`
- 列出本地缓存帖子：`scripts/weibo-cli local list`
- 本地数据库统计：`scripts/weibo-cli local stats`
- 查看逐用户同步覆盖日志：`scripts/weibo-cli local sync-log`
- 查看定时同步策略状态：`scripts/weibo-cli schedule`
- 启用每日定时 sync（默认 08:07，时间线模式，10 页）：`scripts/weibo-cli schedule set`
- 指定时间、页数和保留天数：`scripts/weibo-cli schedule set --hour 8 --minute 30 --pages 10 --retention-days 30`
- 启用逐用户深度同步定时任务：`scripts/weibo-cli schedule set --mode per-user --pages-per-user 5 --retention-days 30`
- 停用并删除定时策略：`scripts/weibo-cli schedule off`

说明：面向最终用户的对话回复默认仍优先使用文本格式；只有在需要稳定字段时才切到 `--json`。

说明：`user`、`following`、`followers` 结果来自本地 TTL 缓存（用户信息 10 分钟、列表 5 分钟），重复查询同一对象不会重复发起网络请求。如需强制刷新，可在命令前加 `WEIBO_CACHE_DISABLED=1`。

说明：`following --all-pages` / `followers --all-pages` 一次性自动翻页拉取全量列表，JSON 输出含 `total` 和 `has_more=false`；单页模式的 JSON 输出含 `has_more`，`true` 表示还有更多页。

更完整的参数示例见 [references/commands.md](references/commands.md)。

## 执行规则

1. 用户未确认最终文本时，不要执行 `post`。
2. 缺少 `weibo-id` 时，不要执行 `reposts`，先向用户索取明确 ID。
3. 缺少 `weibo-id` 时，不要执行 `show`、`comments`、`comment`、`like`、`unlike`、`delete`，先向用户索取明确 ID。
4. 执行任何业务命令前**不要**先调用 `status`；直接执行目标命令，若失败且 `--json` 输出的 `error.category == “auth”`（或 `error.next_action == “login”`），立即执行 `login`（**不要** `login --force`）并重试原命令，不需要额外确认。
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
15. `sync` 每次拉取首页时间线 N 页（默认 5 页，约 100 条），写入 `~/.local/share/weibo-cli/feed.db`，重复帖子自动跳过；`local search` 在本地库中做 LIKE 搜索，**无需联网**，适合离线分析关注用户的历史内容。`local search` 支持 `--days N` 限制最近 N 天的发帖。
16. 用户想在关注用户中按关键词查找帖子时，**正确策略是 sync + local search**，而不是 `search --following-only`：`search --following-only` 仅从全网搜索结果中后置过滤，覆盖上限约 100 条，大量关注用户的帖子可能不在全网 top 100 而漏掉；`sync` 直接拉取关注时间线（私有 API），可拿到所有关注用户最近的帖子。推荐流程：先 `local stats` 确认数据量，若总条数 < 100 或 `newest_synced_at` 超过 1 小时，先执行 `sync --pages 10`，再 `local search --keyword <关键词> --days 7`。
17. 查看某个用户最近发布的微博，使用 `list --uid <UID>`；`list` 不传 `--uid` 则只查当前登录账号自己的微博。**不要**尝试 `search --keyword "from:<UID>"`，该语法不受支持。
18. 用户明确说"我关注的用户里"、"关注的人发了"、"关注用户中"等语境时，优先走 `sync + local search` 流程（见规则 16），不要用无过滤的全网搜索；仅当用户明确需要"最新几分钟内"的实时结果时，才考虑 `search --following-only` 作为补充。
19. 搜索非中文关键词（尤其是人名）时，若返回 0 结果，在报告"无结果"前**必须**主动尝试 1–2 个最可能的正确拼写并重新执行搜索；不要等用户手动纠正后才重试。例：用户输入 "kaaparthy" / "karparthy" → 应自动尝试 "karpathy"。
20. 用户用简短词（"好的"、"是"、"行"、"ok"、"嗯"）回复上一轮提出的操作建议时，直接执行其中**最有价值**的那个操作，不要再次列出选项或征求选择。
21. 用户询问"有没有开定时同步""定时任务状态""有没有每天自动 sync"时，先执行 `schedule` 查看当前策略，再根据结果给出建议。
22. `schedule` 仅在 macOS 下可用（依赖 launchctl）；在非 macOS 环境下执行会报错，告知用户该功能暂不支持当前系统。
23. `sync --per-user` 会遍历全部关注者并逐一抓取其微博（每人 3 页默认），请求间随机延迟 1–3 秒，跳过 6 小时内已同步的用户；适合用于：（a）建立初始全量本地索引、（b）定期深度补抓时间线遗漏的帖子。关注数较多时可能运行 10 分钟以上，告知用户预计耗时。`--force` 可跳过 skip-hours 限制强制重新同步所有人。
24. 用户想查"某个关注的人最近发了什么关于 X 的微博"时，使用 `local search --keyword X --uid <UID>` 或 `--user-name <昵称>`；不知道 UID 时，先用 `following` 找到对应用户的 UID。
25. 用户询问"per-user 同步了哪些用户""哪些关注的人被同步了"时，执行 `local sync-log` 查看覆盖情况。
26. `--retention-days` 控制本地数据库保留天数（默认 7）；想保留更长历史时，在 sync 命令或 schedule set 中指定，例如 `--retention-days 30`。
27. `list --uid <uid>` 返回空 `items`（exit 0）时，**不要**直接得出"该用户没有发帖"的结论；应立即补一步 `local list --uid <uid> --limit 20` 确认本地缓存。若本地也为空，再用 `user --uid <uid>` 查 `statuses_count`：若该值 > 0 说明用户确有发帖但当前 API 无法返回（隐私设置或接口限制），告知用户并建议执行 `sync --per-user --force` 深度抓取。
28. 查看某位关注用户的最近动态时，**先查本地缓存**（`local list --uid <uid> --limit 20`）；若本地有数据且 `synced_at` 在 2 小时内，直接用本地结果回复；只有本地无数据或数据明显过旧时，再发起 `list --uid` 网络请求。
29. `sync` 或任何网络请求失败后，本地数据仍然可用——不要因为 `sync` 失败就放弃整个查询；`local search/list` 完全离线运行，在网络或 API 出现问题时应作为首选回退。
30. 命令路径统一使用 `scripts/weibo-cli`（相对于 skill 目录），不要用 `./scripts/weibo-cli` 或绝对路径。

## 完成前检查

- `status` 成功时，应看到“已配置 / 可直接使用 / 来源 / UID / 更新时间”等状态信息。
- `login` 成功时，终端应出现“登录态已写入”并输出 UID。
- `post` 成功时，终端应出现“发布成功”并返回微博 ID。
- `show` 成功时，应看到微博 ID、正文、作者和互动计数。
- `list` 成功时，输出应包含微博 ID 和正文；若是转发微博，还应看到原微博内容；`list --uid <UID>` 可查看任意用户的最近微博。若输出"未查询到微博记录（API 返回空列表）"，需进一步执行 `local list --uid` 和 `user --uid` 验证，不能直接认定用户无帖子。
- `comments` 成功时，输出应包含评论用户、时间和正文；若无结果，应明确说明没有可返回的评论记录。
- `comment` 成功时，终端应出现“评论成功”并返回评论 ID。
- `like` / `unlike` / `delete` 成功时，应返回目标微博 ID 和操作结果说明。
- `reposts` 成功时，输出应包含转发用户、时间、来源和正文；若无结果，应明确说明没有可返回的转发记录。
- `user` 成功时，应看到昵称、UID、粉丝数、关注数、微博数，以及简介、认证信息（如有）。
- `following` / `followers` 成功时，应看到带编号的用户列表（昵称、UID、粉丝数等）；`--all-pages` 时还应看到合计条数；若 `items` 为空列表（exit 0），告知用户"未能获取到关注/粉丝列表，该功能可能处于不可用状态"，并报告给开发者。
- `search` 成功时，应看到带编号的微博列表（微博 ID、作者、互动计数、正文）；若无结果，应明确说明未找到相关微博。
- `sync` 成功时，应看到新增条数、跳过条数、过期清理条数、数据库总计及路径。
- `sync --per-user` 成功时，应看到"逐用户同步完成"、处理用户数（含跳过/失败）、新增条数及数据库总计。
- `local search --uid/--user-name` 成功时，输出标题应包含"用户：<过滤条件>"。
- `local sync-log` 成功时，应看到带编号的用户列表（昵称、UID、上次同步时间、新增条数、本地总条数）；若无记录，说明尚未执行过 `sync --per-user`。
- `schedule` 成功时，应看到"状态（已启用/未配置）"、触发时间、同步页数、日志路径等信息。
- `schedule set` 成功时，状态应显示"已启用"，并确认触发时间和页数。
- `schedule off` 成功时，应看到"定时同步策略已停用并删除"并确认状态变为"未配置"。
- `local search` 成功时，应看到带编号的微博列表（含"同步"时间戳）；若无结果，应说明本地数据库中未找到相关内容，并建议先执行 `sync --pages 10` 后重试；`--days N` 生效时，还会输出 `since_days` 字段。
- `local list` 成功时，应看到带编号的微博列表（含"同步"时间戳）；若无结果，说明本地数据库中无符合条件的内容。
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