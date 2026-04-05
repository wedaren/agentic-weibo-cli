# agentic-weibo-cli

面向个人账号的本地单用户微博命令行工具，支持本地浏览器扫码登录、加载本地登录态、发布微博、查看微博详情、查看个人微博列表、查询评论与转发、发表评论、点赞、取消点赞，以及删除自己发布的微博。

这个仓库现在本身就是一个单一标准 skill 目录：根目录直接包含 `SKILL.md`、`scripts/`、`references/`、`evals/` 与 `requirements.txt`。既可以直接作为 Agent Skills skill 使用，也可以通过内置 CLI 执行微博操作。

当前实现的模块分层、调用链与会话模型见 [references/architecture.md](/Users/wedaren/.agents/skills/agentic-weibo-cli/references/architecture.md)。
CLI 与 skill 的整合规范见 [references/cli-skill-conventions.md](/Users/wedaren/.agents/skills/agentic-weibo-cli/references/cli-skill-conventions.md)。

## 环境要求

- Python `>=3.14`
- Node.js `>=20`（仅用于 `npm run ...` 便捷脚本）
- npm
- 本地可访问微博登录页与 `m.weibo.cn`

## 安装与启动

```bash
npm install
npm run help
```

CLI 入口：

```bash
npm run cli -- --help
```

初始化 Python skill 运行环境：

```bash
npm run skills:venv
```

如果不想通过 npm，也可以直接执行：

```bash
python3 -m venv .venv
.venv/bin/python3 -m pip install -r requirements.txt
```

Skills 入口：

```bash
npm run cli -- skills
npm run cli -- skills show agentic-weibo-cli
npm run cli -- skills prompt
npm run cli -- skills validate
npm run evals:init -- --workspace ../agentic-weibo-cli-workspace --iteration 1
npm run smoke
```

## 本地配置说明

配置优先级：

1. 环境变量 `WEIBO_COOKIE` / `WEIBO_UID`
2. 本地未提交文件 `.local/weibo-session.json`

可用环境变量：

- `WEIBO_COOKIE`：完整浏览器 Cookie 字符串，至少建议包含 `SUB`、`SUBP`、`SCF` 之一
- `WEIBO_UID`：当前账号 UID，可选
- `WEIBO_CLI_DATA_DIR`：本地配置目录，默认是仓库下的 `.local/`
- `WEIBO_BROWSER_PROFILE_DIR`：浏览器自动化登录的持久化资料目录，默认是 `.local/browser-profile`
- `WEIBO_API_BASE_URL`：微博接口根地址，默认 `https://m.weibo.cn`

默认本地登录态文件示例：

```json
{
  "version": 2,
  "uid": "1234567890",
  "login_url": "https://passport.weibo.com/sso/signin?entry=wapsso&source=wapssowb&url=https%3A%2F%2Fweibo.com",
  "updated_at": "2026-04-04T07:50:03.907218Z",
  "cookies": [
    {
      "name": "SUB",
      "value": "...",
      "domain": ".weibo.com",
      "path": "/",
      "expires": 1777880106,
      "secure": true,
      "http_only": true
    }
  ]
}
```

`.local/` 和 `.env` 已加入 `.gitignore`，不要把真实 Cookie 提交到仓库。

读取时仍兼容旧格式 `cookie` / `cookieJar`，但当前版本写回本地时统一使用上面的结构化 schema。

## 架构概览

当前实现按职责拆成五层：

- 入口层：`scripts/weibo-cli`、`scripts/weibo_cli/cli.py`
- 鉴权层：`scripts/weibo_cli/auth.py`
- 传输层：`scripts/weibo_cli/api_client.py`
- 业务层：`scripts/weibo_cli/service.py`
- 存储层：`scripts/weibo_cli/session.py`、`scripts/weibo_cli/local_config.py`

浏览器登录适配位于 `scripts/weibo_cli/browser_login.py`，Skill 元数据发现与输出位于 `scripts/weibo_cli/skill_catalog.py`。

典型调用链如下：

```text
CLI -> AuthService -> SessionStore / ApiClient -> Weibo API -> Service normalization -> Output
```

更完整的分层职责、登录链路和 cookie 处理策略见 [references/architecture.md](/Users/wedaren/.agents/skills/agentic-weibo-cli/references/architecture.md)。

## CLI 规范

当前仓库按“可人用、可脚本化、可被 agent 调用”的完整 CLI + skill 项目维护，默认遵循这些约定：

- 正常结果写到 stdout，错误写到 stderr
- 成功返回退出码 `0`，失败返回非 `0`
- 退出码按类型分层：`2` 参数错误，`3` 鉴权失败，`4` 接口/运行失败，`5` 网络失败，`10` 内部错误
- 默认输出面向人类阅读的文本；追加 `--json` 后输出稳定的机器可读 JSON
- 配置优先级固定为：环境变量 > 本地 `.local/weibo-session.json`
- 默认非交互，只有显式传 `--prompt` 才要求终端输入 cookie
- 破坏性动作由 skill 层负责先确认、再调用 CLI
- 评估与回归通过 `evals/` 和 `npm run evals:init` 一起管理

适合自动化调用的例子：

```bash
npm run cli -- status --json
npm run cli -- list --limit 5 --json
npm run cli -- skills validate --json
```

## 扫码登录

先运行：

```bash
npm run cli -- login
```

默认情况下，该命令会：

- 自动打开本地 Chrome/Chromium 到微博登录页
- 默认复用 `.local/browser-profile` 作为自动化浏览器资料目录，而不是每次创建全新临时浏览器
- 等待你在浏览器里扫码完成登录
- 自动提取浏览器中的微博登录 cookie
- 把登录态写入 `.local/weibo-session.json`

如果你要显式指定浏览器资料目录：

```bash
npm run cli -- login --browser-user-data-dir .local/browser-profile
```

检查浏览器自动化依赖是否可用：

```bash
npm run cli -- login --check-browser
```

如果你已经有 Cookie，可以直接写入本地配置：

```bash
WEIBO_COOKIE='SUB=...; SUBP=...; SCF=...' WEIBO_UID='1234567890' npm run cli -- login --from-env
```

手动降级模式：

```bash
npm run cli -- login --manual
```

## 命令示例

查看帮助：

```bash
npm run help
```

查看可用 skills：

```bash
npm run cli -- skills
```

查看某个 skill 文档：

```bash
npm run cli -- skills show agentic-weibo-cli
```

输出适合 agent 注入的 `<available_skills>` XML：

```bash
npm run cli -- skills prompt
```

校验当前仓库的 skills 是否符合规范：

```bash
npm run skills:validate
```

获取机器可读状态输出：

```bash
npm run cli -- status --json
```

初始化第一轮评估 workspace：

```bash
npm run evals:init -- --workspace ../agentic-weibo-cli-workspace --iteration 1
```

如果你要把旧版 skill 快照作为对照组：

```bash
npm run evals:init -- --workspace ../agentic-weibo-cli-workspace --iteration 2 --baseline old_skill --snapshot-old-skill
```

执行一轮无副作用本地自检：

```bash
npm run smoke
```

发布微博：

```bash
npm run cli -- post --text "test from cli"
```

查看指定微博详情：

```bash
npm run cli -- show --weibo-id 1234567890123456
```

查看自己最近发布的微博：

```bash
npm run cli -- list --limit 5 --page 1
npm run cli -- list --limit 20 --only-reposts
npm run cli -- list --limit 20 --only-originals
```

其中：

- `--only-reposts` 用于直接查看最近转发过的微博。
- `--only-originals` 用于只看自己原创微博。

查看某条微博的评论：

```bash
npm run cli -- comments --weibo-id 1234567890123456 --limit 20 --page 1
```

发表评论：

```bash
npm run cli -- comment --weibo-id 1234567890123456 --text "收到，支持你"
```

点赞或取消点赞：

```bash
npm run cli -- like --weibo-id 1234567890123456
npm run cli -- unlike --weibo-id 1234567890123456
```

删除自己发布的微博：

```bash
npm run cli -- delete --weibo-id 1234567890123456
```

查询某条微博的转发：

```bash
npm run cli -- reposts --weibo-id 1234567890123456 --limit 20 --page 1
```

## 常见失败与排查

- 未配置登录态：先执行 `npm run cli -- login`，或设置 `WEIBO_COOKIE`
- Cookie 格式错误：应为完整请求头字符串，例如 `SUB=...; SUBP=...`
- 登录态过期：重新运行 `login` 更新本地文件
- 请求被风控或接口变化：CLI 会返回明确的 HTTP 错误或鉴权错误信息

## 已验证能力

在 2026-04-04 的本地实测中，以下链路已完成真实验证：

- `login`：真实浏览器扫码成功，能提取并写回本地登录态
- `post`：真实发布成功，并返回微博 ID、BID 和访问链接
- `show`：可读取指定微博详情，并展示作者、正文与互动计数
- `list`：能读取最近微博，并正确展示原创和转发内容
- `comments`：可读取指定微博评论，并稳定区分空结果与接口错误
- `reposts`：能查询指定微博转发；当无数据时返回稳定空结果提示
- `login --from-env`：已验证可以使用环境变量中的 cookie/uid 重新写入本地登录态

同一轮验证中还修复了一个实际缺陷：登录态探测请求此前未正确携带 cookie，导致 `login --from-env` 可能误判登录态失效；当前版本已修复。

## Skills 规范

当前仓库只提供 1 个总 skill：根目录的 [SKILL.md](/Users/wedaren/.agents/skills/agentic-weibo-cli/SKILL.md)。

- `agentic-weibo-cli`：统一处理微博登录、发微博、列微博、查转发

这些文档既可以直接阅读，也可以通过 CLI 查看：

```bash
npm run cli -- skills
npm run cli -- skills show agentic-weibo-cli
```

项目当前遵循 Agent Skills 与 `vercel-labs/skills` 的通用约定，且仓库根目录就是 skill 根目录：

- 每个 skill 是一个可分发目录，至少包含一个 `SKILL.md`
- `SKILL.md` 必须带 YAML frontmatter，至少包含 `name` 和 `description`
- `name` 必须与分发后的 skill 目录同名；如果要单独分发，建议目录名与 frontmatter 中的 `name` 保持一致
- agent 可发现的信息以 `SKILL.md` 为唯一事实来源，CLI 不再在 TS 代码里手工重复维护一份元数据
- 当前 skill 会优先通过相对路径调用自身目录下的 `scripts/weibo-cli`，不依赖 `npm run cli -- ...`
- 包装脚本会优先使用根目录 `.venv/bin/python3`；若该虚拟环境不存在，则自动初始化运行环境

如果你后续要扩展更多能力，优先在 `agentic-weibo-cli` 这个总 skill 中补充命令选择规则与 references；只有当新能力已经明显超出“微博 CLI 使用方法”这一边界时，再拆新的 skill。

### skill 根目录中的 CLI 如何组织

当前仓库采用“稳定包装入口 + Python 模块实现”分离：

- `scripts/weibo_cli/`：Python 实现源码
- `scripts/weibo-cli`：给 agent 调用的稳定包装入口
- `.venv/`：skill 本地虚拟环境，安装 `requests` 与 `playwright`

这个仓库不再维护内层 skill 源目录；根目录自身就是唯一 skill，所有 CLI 业务实现都收敛到 `scripts/weibo_cli/`。

## MVP 验收命令

构建与帮助：

```bash
npm run build
npm run help
```

未登录时快速失败：

```bash
npm run cli -- post --text "test from cli"
```

配置好登录态后的联调命令：

```bash
npm run cli -- post --text "test from cli"
npm run cli -- list --limit 5
npm run cli -- reposts --weibo-id <id> --limit 20
```

无副作用自检命令：

```bash
npm run smoke
```

任务验收命令：

```bash
grep -q '扫码登录' README.md && grep -q 'login' README.md && grep -q 'post' README.md && echo PASS || echo 'FAIL: README 缺少扫码登录或命令说明'
```

## 风险说明

- 本项目依赖用户自己提供的微博登录态，不提供 OAuth 或多账号管理
- Cookie 属于敏感凭据，只能保存在本地未提交文件或临时环境变量中
- 微博页面结构、接口字段和风控策略可能变化，命令可能返回接口失败原因而不是稳定成功
- `login` 使用本地浏览器自动提取登录态，不会把二维码内容或 Cookie 上传到仓库
