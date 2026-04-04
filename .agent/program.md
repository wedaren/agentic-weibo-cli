# program.md — 个人微博 CLI

<!-- 
这是项目的唯一事实来源。
- 所有 agent 只读这个文件，不修改它
- 你需要填写：目标、约束、停止条件
- 模糊的地方留着，PM Agent 会帮你补全
-->

## 目标

做一个面向个人账号使用的微博命令行工具，支持扫码登录或加载已有登录态、发布微博、查看自己发过的微博，并获取某条微博的转发信息。

---

## 系统组成

- 单一 skill 文档：`skills/weibo-cli/SKILL.md` 作为 agent 发现入口，描述何时使用、如何选命令、如何验证成功
- CLI 命令入口：通过 `skills/weibo-cli/scripts/weibo-cli` 提供 `login`、`post`、`list`、`reposts`、`skills` 子命令
- Python 实现模块：所有业务实现统一放在 `skills/weibo-cli/scripts/weibo_cli/`
- 配置模块：管理 cookie、用户 ID、默认分页参数等本地配置
- 扫码登录模块：负责打开本地浏览器、轮询登录状态、在成功后持久化登录态
- 会话/认证模块：读取并校验个人微博登录态，负责 cookie 注入、失效检测、错误提示，并兼容扫码登录产物
- 微博 API 客户端：负责请求微博接口、统一处理鉴权、分页、限流和错误信息
- 微博服务层：封装 `post`、`list`、`reposts` 等业务动作，避免 CLI 直接拼接口
- 输出模块：以终端友好的简洁文本展示微博列表和转发信息

---

## 约束（不能动的）

- 只做本地单用户 CLI，不做 Web 页面，不做多用户账号系统
- 优先使用 Python 实现，并把所有业务源码收敛到 `skills/weibo-cli/scripts/weibo_cli/`
- 保留 `npm run ...` 作为仓库便捷入口，但 skill 必须能优先通过相对路径 `scripts/weibo-cli` 独立调用
- 不依赖第三方付费服务或额外 API key；微博访问基于用户自己提供的登录态
- 登录态等敏感信息不能硬编码进仓库，必须通过环境变量或本地未提交配置文件读取
- 扫码登录必须在本地浏览器/终端环境完成，登录 cookie 不能上传到仓库
- MVP 阶段先支持个人账号常用能力，不做自动化养号、批量群发、定时任务
- 输出以可读、稳定、便于脚本二次处理为目标，错误信息需要明确
- 鉴权、接口调用、命令解析、格式化输出必须分层，禁止全部揉在一个文件里
- 运行依赖优先放在 skill 本地虚拟环境 `skills/weibo-cli/.venv/`，避免依赖系统 Python 全局环境

---

## 停止条件（MVP 验收标准）

<!-- 每条必须是可以用命令验证的 -->

- [ ] `npm run help` 能展示 CLI 用法和可用命令
- [ ] `npm run build` 无报错
- [ ] `npm run cli -- skills validate` 能通过，且 `npm run cli -- skills prompt` 能输出可注入的 `<available_skills>` XML
- [ ] `npm run cli -- login` 能启动本地登录流程，并在登录成功后把登录态写入本地配置
- [ ] 未配置微博登录态时，`npm run cli -- post --text "test from cli"` 会快速失败并提示如何配置
- [ ] 配置好微博登录态后，`npm run cli -- post --text "test from cli"` 能成功发布微博或返回清晰的接口失败原因
- [ ] 配置好微博登录态后，`npm run cli -- list --limit 5` 能列出当前账号最近发布的微博或返回清晰的接口失败原因
- [ ] 配置好微博登录态后，`npm run cli -- reposts --weibo-id <id> --limit 20` 能获取指定微博的转发信息或返回清晰的接口失败原因
- [ ] README 和 SKILL.md 包含本地配置方式、命令示例、skill 用法和风险说明

---

## 技术选型（PM Agent 默认决策，可 [OVERRIDE]）

<!-- PM Agent 会在 task_000 research 后填充这里 -->

- [OVERRIDE] 默认使用 Python + argparse + requests + Playwright，同步保留根目录 npm 便捷脚本
- [OVERRIDE] skill 元数据以 `SKILL.md` frontmatter 为唯一事实来源，不再在业务代码中维护一份重复技能目录
- [OVERRIDE] 配置优先级：环境变量 > 本地配置文件
- [OVERRIDE] 输出优先保证可读性，其次再考虑 JSON 模式

---

## 功能进化区（MVP 完成后持续追加）

<!--
使用方式：
1. 在下面追加功能想法，格式随意，可以很模糊
2. 保存文件
3. bash evolve.sh 自动检测并开始实现

状态：
- [ ] 待处理
- [~] 进行中（系统自动标记）
- [x] 已完成（系统自动标记）
-->

### 待实现功能

- [ ] 增加 `delete` 命令，支持删除自己发布的微博
- [ ] 增加 `show` 命令，查看单条微博完整详情
- [ ] 支持 JSON 输出模式，便于 shell 脚本消费
- [ ] 支持从文件读取长文本并发微博
- [ ] 支持查看评论信息
- [ ] 支持导出或清除本地登录态
