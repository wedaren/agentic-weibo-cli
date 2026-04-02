## 结论（3 句话以内）
MVP 采用 Node.js + TypeScript + Commander.js + 原生 `fetch`/Undici 的组合，满足 CLI 分层、轻量和无额外运行时约束。CLI 入口走 npm script + `package.json#bin`，配置层优先环境变量，再落到本地未提交配置文件。扫码登录相关二维码展示可优先采用终端二维码库，HTTP 调用不额外引入大型 SDK。

## 关键 API / 配置
- Commander.js：使用 `Command`、`.command()`、`.option()`、`.requiredOption()`、`.parseAsync()` 组织多子命令 CLI。
- Node.js：优先用内建 `fetch` 发送微博请求；需要连接池或流式能力时再下沉到 Undici 的 `Pool`/`stream`。
- npm：在 `package.json` 使用 `bin` 暴露 CLI 可执行入口，入口文件需带 `#!/usr/bin/env node`。
- 配置存储：本地配置可使用 `conf` 这类基于系统用户配置目录的方案；敏感字段不入仓库，文件权限可收紧到 `0o600`。
- 终端二维码：`qrcode-terminal` 支持直接把二维码内容渲染到终端，适合本地扫码登录指引。

## 注意事项
- `fetch` 已足够覆盖 MVP 的 JSON 请求和错误处理；只有在需要细粒度连接复用时才引入 Undici 高级 API。
- `conf` 的“加密”更偏向混淆，不应视为真正的密钥保护；登录态仍需通过 `.gitignore` 和本地权限控制保护。
- CLI 可读输出优先，JSON 输出模式放到后续演进功能实现。

## 来源
- 官方：Commander.js README, https://github.com/tj/commander.js
- 官方：Node.js Fetch 文档, https://nodejs.org/en/learn/getting-started/fetch
- 官方：npm package.json `bin` 文档, https://docs.npmjs.com/cli/v11/configuring-npm/package-json/#bin
- 官方/项目 README：Conf, https://github.com/sindresorhus/conf
- 官方/项目 README：qrcode-terminal, https://github.com/gtanner/qrcode-terminal

## 可信度：高
