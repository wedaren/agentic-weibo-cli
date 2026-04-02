## 结论（3 句话以内）
登录集成优先采用本地浏览器驱动完成官方网页登录/扫码，再把 cookies 或 storage state 保存到本地未提交文件；这条路径比直接对未公开二维码接口做轮询更稳。微博内容读写层不要绑定微博开放平台 OAuth 方案，因为该方案普遍要求 `access_token`、应用配置，且发布类接口还有额外平台约束，与“无额外 API key、基于用户自带登录态”的项目约束不完全匹配。MVP 应把“扫码登录产物 -> 会话校验 -> cookie 注入 -> 请求 `post/list/reposts`”作为关键集成链路。

## 关键 API / 配置
- Playwright：
  - 登录后调用 `page.context().storageState({ path })` 保存认证状态
  - 需要显式提醒把认证文件加入 `.gitignore`
  - 如只需 cookies，可用 `browserContext.cookies()` 读取并转为请求头
- 微博开放平台参考：
  - `statuses/update`
  - `statuses/user_timeline`
  - `statuses/repost_timeline`
  - 社区资料反复表明这些接口围绕 `access_token`/应用接入设计
- 本项目实现建议：
  - 配置层保存 cookies、uid、默认 limit/page
  - 认证层负责 cookie 失效检测和错误提示
  - API 客户端统一注入 `Cookie`、`User-Agent`、分页参数与限流

## 注意事项
- Playwright 官方文档明确提示认证状态文件包含敏感 cookies，不能提交到仓库。
- 这里对微博开放平台限制的判断，来自较新的平台公告线索和多份社区资料交叉验证；由于官方技术文档检索可见性较差，这部分可信度定为中。
- 需要预期微博接口和风控策略会变化，编码阶段要把错误归一、限流和登录失效提示做成显式分支。

## 来源
- 官方：Playwright Authentication, https://playwright.dev/docs/auth
- 官方：Playwright BrowserContext `storageState` / `cookies`, https://playwright.dev/docs/api/class-browsercontext
- 社区交叉验证：Go Weibo package docs 引用官方 endpoints, https://pkg.go.dev/github.com/larrylv/go-weibo/weibo
- 社区交叉验证：微博接口接入说明与发布类接口限制讨论, https://www.cnblogs.com/me115/p/3451681.html
- 社区交叉验证：微博开放平台相关接口与限制讨论, https://www.cnblogs.com/learcher/articles/7171891.html
- 辅助线索：微博开放平台官方账号公告聚合页, https://www.weibo.com/openapi

## 可信度：中
