# agentic-weibo-cli

面向个人账号的本地单用户微博命令行工具，支持扫码登录指引、加载本地登录态、发布微博、查看个人微博列表，以及查询指定微博的转发信息。

## 环境要求

- Node.js `>=20`
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

## 本地配置说明

配置优先级：

1. 环境变量 `WEIBO_COOKIE` / `WEIBO_UID`
2. 本地未提交文件 `.local/weibo-session.json`

可用环境变量：

- `WEIBO_COOKIE`：完整浏览器 Cookie 字符串，至少建议包含 `SUB`、`SUBP`、`SCF` 之一
- `WEIBO_UID`：当前账号 UID，可选
- `WEIBO_CLI_DATA_DIR`：本地配置目录，默认是仓库下的 `.local/`
- `WEIBO_API_BASE_URL`：微博接口根地址，默认 `https://m.weibo.cn`

默认本地登录态文件示例：

```json
{
  "cookie": "SUB=...; SUBP=...; SCF=...",
  "uid": "1234567890",
  "loginUrl": "https://passport.weibo.com/signin/login?entry=mweibo&r=https%3A%2F%2Fm.weibo.cn%2F",
  "updatedAt": "2026-04-02T16:00:00.000Z"
}
```

`.local/` 和 `.env` 已加入 `.gitignore`，不要把真实 Cookie 提交到仓库。

## 扫码登录

先运行：

```bash
npm run cli -- login
```

该命令会：

- 在终端输出扫码登录指引
- 渲染微博登录页二维码
- 提示你在扫码成功后，把浏览器里的完整 Cookie 粘贴回终端
- 把登录态写入 `.local/weibo-session.json`

如果你已经有 Cookie，可以直接写入本地配置：

```bash
WEIBO_COOKIE='SUB=...; SUBP=...; SCF=...' WEIBO_UID='1234567890' npm run cli -- login --from-env
```

或：

```bash
npm run cli -- login --cookie 'SUB=...; SUBP=...; SCF=...' --uid 1234567890 --no-prompt
```

## 命令示例

查看帮助：

```bash
npm run help
```

发布微博：

```bash
npm run cli -- post --text "test from cli"
```

查看自己最近发布的微博：

```bash
npm run cli -- list --limit 5 --page 1
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

任务验收命令：

```bash
grep -q '扫码登录' README.md && grep -q 'login' README.md && grep -q 'post' README.md && echo PASS || echo 'FAIL: README 缺少扫码登录或命令说明'
```

## 风险说明

- 本项目依赖用户自己提供的微博登录态，不提供 OAuth 或多账号管理
- Cookie 属于敏感凭据，只能保存在本地未提交文件或临时环境变量中
- 微博页面结构、接口字段和风控策略可能变化，命令可能返回接口失败原因而不是稳定成功
- `login` 当前提供的是本地扫码指引和登录态落盘流程，不会把二维码内容或 Cookie 上传到仓库
