## 任务：task_002 第1次
## 从历史学到：骨架和命令入口已稳定，这次应直接补齐登录链路而不是改动 CLI 结构
## 用到的 knowledge：core-tech-stack.md、key-integrations.md、project-structure.md
## 本次假设（与上次核心区别）：用终端二维码 + 手动回填 cookie 的本地流程先完成 MVP 登录闭环，并把会话持久化能力沉到 config/auth 层
## 实现摘要：新增 qrcode-terminal 依赖；login 命令可展示微博登录页二维码、支持交互式或环境变量/参数写入 cookie；新增本地配置读写、会话加载与持久化逻辑，并将登录态写入 .local/weibo-session.json
## 自评分：93/100
## 各维度：核心33/40 | 编译25/25 | 选型20/20 | 约束15/15
## 下次改进方向：在后续任务中补浏览器自动抓取 cookie/校验登录有效性，减少手动复制 cookie 的步骤
