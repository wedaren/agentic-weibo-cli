# Weibo CLI Architecture

本文档描述当前仓库的实际运行架构，用于帮助维护者理解模块边界、调用链和数据流。

## 设计目标

- 单用户、本地执行，不引入服务端状态
- 把登录态管理、HTTP 传输、业务编排、CLI 展示拆开，避免脚本式耦合
- 默认优先复用本地浏览器 profile，减少重复扫码
- 本地会话既能从环境变量读取，也能稳定持久化到 `.local/weibo-session.json`
- 遇到登录失效时，优先返回明确错误，而不是伪装成空结果

## 总体分层

当前实现可以按五层理解：

1. 入口层：命令解析与输出分发
2. 鉴权层：登录态检查、登录流程编排、持久化入口
3. 传输层：微博 HTTP 请求、请求头构造、响应鉴权判定、运行时 cookie 合并
4. 领域层：发微博、列微博、查转发等业务动作与数据归一
5. 存储层：本地 session 文件、浏览器 profile 路径、cookie 模型与序列化

## 模块职责

### 入口层

- `scripts/weibo-cli`
  - shell 包装入口
  - 确保 `.venv` 可用
  - 调用 `python -m weibo_cli.cli`
- `scripts/weibo_cli/cli.py`
  - 注册 `login`、`status`、`post`、`list`、`reposts`、`skills`
  - 负责参数校验和命令分发
  - 负责统一的 `--json` 机器输出契约
  - 不直接实现登录、鉴权或业务逻辑，只调用服务层与输出层
- `scripts/weibo_cli/output.py`
  - 负责把领域对象格式化成稳定终端文本与 JSON 输出

### 鉴权层

- `scripts/weibo_cli/auth.py`
  - 统一对外暴露 `WeiboAuthService`
  - `inspect()` 负责判断“已配置但失效”和“可直接使用”的区别
  - `require_valid_session()` 给业务层返回已验证 session
  - `persist_browser_login()` 编排浏览器登录 -> 校验 -> 持久化
  - `persist_cookie_header()` 编排手工 cookie -> 校验 -> 持久化

### 传输层

- `scripts/weibo_cli/api_client.py`
  - 负责所有 HTTP 请求
  - 统一设置 `User-Agent`、`Cookie`、`XSRF`、`Origin` 等请求头
  - 通过 `/api/config` 探测登录态
  - 同时识别 HTTP 401/403 与业务层 `login=false`、`ok=-100` 等失效信号
  - 把响应中的新 cookie 合并回当前 session，并在本地模式下写回磁盘

### 领域层

- `scripts/weibo_cli/service.py`
  - `post_weibo()`：发布微博
  - `list_own_weibos()`：读取个人微博列表
  - `get_reposts()`：读取指定微博转发
  - 负责把微博接口原始 JSON 归一成稳定的数据对象
  - 负责把 HTML 正文转成纯文本

### 存储层

- `scripts/weibo_cli/session.py`
  - 定义 `CookieRecord`、`SessionData`、`SessionStatus`
  - 负责 cookie 选择优先级、序列化、反序列化、过期校验
  - `SessionStore` 统一处理环境变量和本地文件加载/保存
- `scripts/weibo_cli/local_config.py`
  - 解析 `.local/` 目录、session 文件路径、浏览器 profile 路径
  - 负责本地 JSON 文件读写

### 浏览器登录适配层

- `scripts/weibo_cli/browser_login.py`
  - 基于 Playwright 启动持久化浏览器上下文
  - 默认复用 `.local/browser-profile`
  - 优先尝试复用已有微博登录态，复用失败才进入扫码轮询
  - 提取 `m.weibo.cn`、`weibo.com`、`passport.weibo.com` 下的 cookie

### Skill 元数据层

- `scripts/weibo_cli/skill_catalog.py`
  - 负责发现 `SKILL.md`
  - 输出技能列表、完整文档、XML prompt 和校验结果

## 运行时调用链

### 登录态检查

`status` 的主链路如下：

```text
scripts/weibo-cli
  -> weibo_cli.cli.handle_status()
  -> WeiboAuthService.inspect()
  -> SessionStore.load()
  -> SessionData.assert_auth_cookies()
  -> WeiboApiClient.validate_session()
  -> GET /api/config
  -> output.format_session_status()
```

### 浏览器登录

`login` 默认走浏览器复用/扫码链路：

```text
cli.handle_login()
  -> WeiboAuthService.persist_browser_login()
  -> run_browser_login()
  -> try_reuse_existing_login()
  -> extract_weibo_cookies()
  -> probe_uid()
  -> WeiboApiClient.validate_session()
  -> SessionStore.save()
```

### 业务命令

`list`、`post`、`reposts` 都先经过鉴权层：

```text
cli.handle_list()/handle_post()/handle_reposts()
  -> WeiboService.create_default()
  -> WeiboAuthService.require_valid_session()
  -> WeiboApiClient(...)
  -> service method
  -> 微博业务接口
  -> output formatter
```

## 会话模型

当前本地会话文件使用 `version: 2` 结构化 schema，而不是仅保存一条 cookie header：

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

兼容性说明：

- 读取时仍兼容旧字段 `cookieJar`、`cookie`、`loginUrl`、`updatedAt`
- 写入时统一落到 `version: 2` 的新 schema
- 环境变量模式下不写本地文件，`source` 会标记为 `env`

## Cookie 处理策略

这是当前架构里最关键的一层，原因是微博多个域名下存在同名 cookie。

- 存储层保留完整 cookie 列表，而不是只保留简单 header
- 发送请求时，`SessionData.cookie_header()` 会按名称选出优先 cookie
- 当前优先级按 domain/path/expires 决定，优先保留更适合 `m.weibo.cn` 业务请求的值
- 传输层仍显式发送 `Cookie` 请求头，而不是完全依赖 `requests.Session` 自动挑选

这样做的目的，是避免“cookie 明明存在，但 requests 实际没有按预期发出”的隐性失效问题。

## 登录失效判定

当前实现同时看三类信号：

- 本地快速校验：是否至少包含 `SUB`、`SUBP`、`SCF` 之一，`ALF` 是否过期
- HTTP 层信号：401、403
- 业务层信号：`data.login == false`、`ok == -100`、跳转到 `passport.weibo.com`

这能避免把“未登录”误解释成“空列表”或“接口暂无数据”。

## 为什么默认复用浏览器 profile

旧式“每次用临时浏览器上下文登录”的方案会带来两个问题：

- 用户明明在浏览器里已登录微博，CLI 仍然要求重新扫码
- 浏览器侧真实有效的附加 cookie 无法长期复用

当前实现默认复用 `.local/browser-profile`，并在进入扫码前先访问业务域名测试已有登录态，因此正常情况下不需要重复扫码。

## 目录视图

```text
.
├── SKILL.md
├── README.md
├── references/
│   ├── commands.md
│   └── architecture.md
├── scripts/
│   ├── self-check
│   ├── weibo-cli
│   └── weibo_cli/
│       ├── auth.py
│       ├── api_client.py
│       ├── browser_login.py
│       ├── cli.py
│       ├── local_config.py
│       ├── output.py
│       ├── service.py
│       ├── session.py
│       └── skill_catalog.py
└── tests/
    └── test_session_and_auth.py
```

## 维护建议

- 新增微博能力时，优先加在 `service.py`，不要把接口细节写回 CLI
- 新增登录来源时，优先扩展 `WeiboAuthService`，不要直接在入口层写持久化逻辑
- 如果要调整 cookie 优先级，先看 `session.py` 的 `DOMAIN_PRIORITY` 和 `select_cookie_header_cookies()`
- 如果微博接口返回结构变化，优先修改 `service.py` 的归一逻辑和 `api_client.py` 的鉴权判定
- 文档同步时，README 保持面向使用者，架构细节放到本文件