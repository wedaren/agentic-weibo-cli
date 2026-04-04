# decisions.md — 自动决策日志

格式：`[task_id][时间] 决策：xxx | 原因：xxx | research 依据：knowledge/xxx.md`
如有异议：在行尾加 `[OVERRIDE] 你的意见`

---

<!-- PM Agent 从这里开始追加 -->
[task_000][2026-04-04 10:00:00 CST] 决策：当前主技术栈采用 Python + argparse + requests + Playwright；根目录保留 npm 便捷脚本，但业务实现不再依赖 TypeScript/Node 构建产物。  
原因：仓库已收敛为 skill-first 模型，所有业务实现集中在 skill 目录内，Python 更适合直接以 skill 自带脚本运行，并通过 `.venv` 管理依赖。  
research 依据：knowledge/core-tech-stack.md
如有异议：在行尾加 [OVERRIDE]
---
[task_000][2026-04-04 10:00:00 CST] 决策：项目结构固定为单一 `skills/weibo-cli/` skill，`SKILL.md` frontmatter 作为技能元数据唯一事实来源，CLI Python 源码位于 `skills/weibo-cli/scripts/weibo_cli/`，稳定入口位于 `skills/weibo-cli/scripts/weibo-cli`。  
原因：当前目标是让 agent 优先发现和调用 skill，自描述文档与实现同目录可以减少分叉和路径假设，便于全局分发与独立执行。  
research 依据：knowledge/project-structure.md
如有异议：在行尾加 [OVERRIDE]
---
[task_000][2026-04-04 10:00:00 CST] 决策：扫码登录继续采用本地浏览器驱动抓取登录态并落本地认证文件，不采用微博开放平台 OAuth 作为主接入路径；微博业务请求统一走 cookie 注入的 API 客户端。  
原因：开放平台接口普遍围绕 `access_token`、应用配置和平台限制设计，与“用户自带登录态、无额外 API key”的项目约束不完全一致；浏览器登录态保存仍是最贴合 MVP 的实现。  
research 依据：knowledge/key-integrations.md
如有异议：在行尾加 [OVERRIDE]
---
