# Weibo CLI Commands

首次使用前建议先初始化 skill 本地虚拟环境：

```bash
npm run skills:venv
```

如果直接运行 `scripts/weibo-cli` 且本地 `.venv` 尚未准备好，包装脚本也会尝试自动创建虚拟环境并安装 `requirements.txt`。

执行一轮无副作用本地自检：

```bash
npm run smoke
```

## 通用约定

- 所有业务命令都支持 `--json`，用于输出稳定的机器可读结果
- 默认输出为面向终端阅读的文本
- 成功时退出码为 `0`，失败时退出码为非 `0`
- 正常结果写到 stdout，错误信息写到 stderr

当前退出码约定：

- `0`：成功
- `2`：参数或命令用法错误
- `3`：鉴权失败或登录态无效
- `4`：业务接口或运行时操作失败
- `5`：网络请求失败
- `10`：未分类内部错误

示例：

```bash
scripts/weibo-cli status --json
scripts/weibo-cli list --limit 5 --json
scripts/weibo-cli skills validate --json
```

## 查看当前登录态状态

```bash
scripts/weibo-cli status
scripts/weibo-cli status --json
```

适用场景：先确认当前是否已登录、登录态是否还可直接使用，避免重复执行 `login`。

## 登录

```bash
scripts/weibo-cli login
scripts/weibo-cli login --force
scripts/weibo-cli login --check-browser
scripts/weibo-cli login --check-browser --json
scripts/weibo-cli login --browser-user-data-dir .local/browser-profile
scripts/weibo-cli login --prompt
WEIBO_COOKIE='SUB=...; SUBP=...; SCF=...' WEIBO_UID='1234567890' scripts/weibo-cli login --from-env
```

适用场景：首次登录、登录态过期、切换账号。

说明：`login` 默认会先检查当前是否已有可用登录态；如果登录态仍有效，会直接返回状态提示而不是重复登录。只有显式传入 `--force` 时，才会忽略当前登录态并重新执行登录流程。`login` 默认复用 `.local/browser-profile` 作为自动化浏览器资料目录，因此同一套 CLI 登录链路在多数情况下不需要每次重新扫码。只有显式传入新的 `--browser-user-data-dir`，或删除该目录后，才会像第一次登录那样从空白浏览器开始。`login` 同时保持非交互默认值，扫码失败时会直接报错并退出，不会卡在终端等待输入。只有显式传入 `--prompt` 时，才会要求手动粘贴 cookie。

说明：如果只想确认本机浏览器自动化和当前登录态读取是否正常，而不执行扫码或发布，可运行 `npm run smoke`。

## 发布微博

```bash
scripts/weibo-cli post --text "test from skill"
scripts/weibo-cli post --text "test from skill" --json
```

要求：文本已经确认，不为空。

## 查看指定微博详情

```bash
scripts/weibo-cli show --weibo-id 1234567890123456
scripts/weibo-cli show --weibo-id 1234567890123456 --json
```

适用场景：查看某条微博正文、来源、作者和互动计数，确认要评论、点赞或删除的目标是否正确。

## 查看最近微博

```bash
scripts/weibo-cli list --limit 5 --page 1
scripts/weibo-cli list --limit 20 --only-reposts
scripts/weibo-cli list --limit 20 --only-originals
scripts/weibo-cli list --limit 5 --json
```

适用场景：确认刚发出的微博、查看最近动态、检查转发原文。

补充说明：

- `--only-reposts` 适合直接查看“最近转发的微博”，避免让上层 agent 先拉全量再自行筛选。
- `--only-originals` 适合排除转发，只看自己原创内容。

## 查询转发

```bash
scripts/weibo-cli reposts --weibo-id 1234567890123456 --limit 20 --page 1
scripts/weibo-cli reposts --weibo-id 1234567890123456 --limit 20 --page 1 --json
```

要求：必须提供明确的微博 ID。

## 查询评论

```bash
scripts/weibo-cli comments --weibo-id 1234567890123456 --limit 20 --page 1
scripts/weibo-cli comments --weibo-id 1234567890123456 --limit 20 --page 1 --json
```

适用场景：查看指定微博下的最新评论，确认某条互动是否已经出现。

## 发表评论

```bash
scripts/weibo-cli comment --weibo-id 1234567890123456 --text "收到，支持你"
scripts/weibo-cli comment --weibo-id 1234567890123456 --text "收到，支持你" --json
```

要求：必须提供明确的微博 ID，且评论文本已经确认。

## 点赞与取消点赞

```bash
scripts/weibo-cli like --weibo-id 1234567890123456
scripts/weibo-cli unlike --weibo-id 1234567890123456
scripts/weibo-cli like --weibo-id 1234567890123456 --json
```

适用场景：对指定微博表达支持，或撤销此前的点赞操作。

## 删除自己发布的微博

```bash
scripts/weibo-cli delete --weibo-id 1234567890123456
scripts/weibo-cli delete --weibo-id 1234567890123456 --json
```

要求：只在用户明确要求删除时执行；删除属于不可逆操作，执行前应再次确认目标微博 ID。

## 查看用户信息

```bash
scripts/weibo-cli user --uid <UID>
scripts/weibo-cli user --uid <UID> --json
```

参数：
- `--uid`（必填）：目标用户的 UID

返回字段（JSON 时）：uid、screen_name、description、location、followers_count、friends_count、statuses_count、verified、verified_reason、profile_url

结果来自本地 TTL 缓存（10 分钟），重复查询同一用户不会重复请求网络。

## 查看关注列表

```bash
scripts/weibo-cli following
scripts/weibo-cli following --all-pages --json
scripts/weibo-cli following --uid <UID> --all-pages --json
scripts/weibo-cli following --uid <UID> --page 2 --json
```

参数：
- `--uid`（可选）：目标用户 UID；不填则查询当前登录账号
- `--all-pages`（可选）：自动翻页拉取全量关注列表（**agent 优先使用此选项**，避免手动循环翻页）
- `--page`（可选，默认 1）：单页翻页，不与 `--all-pages` 同时使用

返回字段（`--json` 时）：uid、items、has_more（单页时，len(items)==20 推断为 true）；`--all-pages` 时还包含 total、all_pages=true、has_more=false

结果来自本地 TTL 缓存（5 分钟）。

## 搜索微博

```bash
scripts/weibo-cli search --keyword karpathy
scripts/weibo-cli search --keyword karpathy --following-only
scripts/weibo-cli search --keyword karpathy --following-only --limit 10 --json
scripts/weibo-cli search --keyword karpathy --page 2 --json
```

参数：
- `--keyword`（必填）：搜索关键词
- `--following-only`（可选）：仅返回你关注的用户发布的结果；开启后自动翻页（最多 5 页）以凑够 limit 条
- `--limit`（可选，默认 20）：最多返回条数
- `--page`（可选，默认 1）：页码，仅在不带 `--following-only` 时生效

返回字段（`--json` 时）：keyword、following_only、items（同 list 命令的 item 结构，含 user_name/user_id）

说明：`--following-only` 过滤基于微博搜索结果中的 `user.following` 字段（client-side 过滤），因此结果数量取决于关注用户在全网搜索结果中的占比；关注用户越少、关键词越热门，每页有效结果越稀少。

## 查看粉丝列表

```bash
scripts/weibo-cli followers
scripts/weibo-cli followers --all-pages --json
scripts/weibo-cli followers --uid <UID> --all-pages --json
scripts/weibo-cli followers --uid <UID> --page 2 --json
```

参数：
- `--uid`（可选）：目标用户 UID；不填则查询当前登录账号
- `--all-pages`（可选）：自动翻页拉取全量粉丝列表（**agent 优先使用此选项**）
- `--page`（可选，默认 1）：单页翻页，不与 `--all-pages` 同时使用

返回字段（`--json` 时）：uid、items、has_more；`--all-pages` 时还包含 total、all_pages=true

结果来自本地 TTL 缓存（5 分钟）。