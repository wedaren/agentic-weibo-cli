# decisions.md — 自动决策日志

格式：`[task_id][时间] 决策：xxx | 原因：xxx | research 依据：knowledge/xxx.md`
如有异议：在行尾加 `[OVERRIDE] 你的意见`

---

<!-- PM Agent 从这里开始追加 -->
[task_000][2026-04-02 23:19:08 CST] 决策：MVP 技术栈采用 Node.js + TypeScript + Commander.js + 原生 fetch/Undici；配置优先环境变量，其次本地未提交配置文件。  
原因：满足 program.md 的 Node.js/TypeScript 约束，CLI 方案轻量，HTTP 能力足够，且不引入额外 API key 或重型运行时。  
research 依据：knowledge/core-tech-stack.md
如有异议：在行尾加 [OVERRIDE]
---
[task_000][2026-04-02 23:19:08 CST] 决策：项目结构固定拆分为 `bin`/CLI 入口、`src/commands`、`src/services`、`src/api`、`src/auth`、`src/config`、`src/output`，编译产物输出到 `dist/`。  
原因：program.md 明确要求鉴权、接口调用、命令解析、格式化输出分层；该结构能直接支撑 `login`、`post`、`list`、`reposts` 四条命令的增量实现。  
research 依据：knowledge/project-structure.md
如有异议：在行尾加 [OVERRIDE]
---
[task_000][2026-04-02 23:19:08 CST] 决策：扫码登录采用本地浏览器驱动抓取登录态并落本地认证文件，不采用微博开放平台 OAuth 作为主接入路径；微博业务请求统一走 cookie 注入的 API 客户端。  
原因：开放平台接口普遍围绕 `access_token`、应用配置和平台限制设计，与“用户自带登录态、无额外 API key”的项目约束不完全一致；浏览器登录态保存更贴合 MVP。  
research 依据：knowledge/key-integrations.md
如有异议：在行尾加 [OVERRIDE]
---
