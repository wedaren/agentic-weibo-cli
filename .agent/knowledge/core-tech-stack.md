## 结论（3 句话以内）
当前仓库采用 Python + argparse + requests + Playwright 的组合实现微博 CLI，所有业务实现都收敛在单一 `weibo-cli` skill 目录中。根目录 `package.json` 只承担便捷脚本和 bin 暴露职责，真正稳定入口是 `skills/weibo-cli/scripts/weibo-cli`。依赖优先安装到 `skills/weibo-cli/.venv/`，配置优先环境变量，其次本地未提交配置文件。

## 关键 API / 配置
- argparse：用于注册 `login`、`post`、`list`、`reposts`、`skills` 子命令，并维持标准帮助输出。
- requests：负责微博 HTTP 请求、cookie 注入、错误归一与基础限流。
- Playwright（Python）：负责本地浏览器自动化登录和 cookie 抓取。
- Python venv：通过 `skills/weibo-cli/.venv/` 隔离 skill 运行依赖，避免污染系统 Python。
- npm：保留 `npm run help`、`npm run cli -- ...`、`npm run skills:venv` 作为仓库级便捷入口。

## 注意事项
- 真正给 agent 调用的入口应是 `scripts/weibo-cli`，不能把仓库根目录 `npm run cli -- ...` 当成唯一执行方式。
- `compileall` 只用于快速语法校验，不是分发产物；`__pycache__` 和 `*.pyc` 不应纳入版本控制。
- Playwright Python 依赖内部仍会携带 Node driver，但这不改变本仓库“业务实现是 Python”的事实。
- 登录态仍需通过 `.gitignore`、本地文件权限和环境变量保护，不应入仓库。

## 来源
- 官方：Python argparse 文档, https://docs.python.org/3/library/argparse.html
- 官方：Requests 文档, https://requests.readthedocs.io/
- 官方：Playwright for Python 文档, https://playwright.dev/python/
- 官方：Python venv 文档, https://docs.python.org/3/library/venv.html

## 可信度：高
