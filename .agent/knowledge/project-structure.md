## 结论（3 句话以内）
当前项目结构应围绕单一 `weibo-cli` skill 组织，而不是围绕仓库级 `src/` 目录组织。skill 文档、包装入口、Python 实现、参考命令和本地虚拟环境都收敛在 `skills/weibo-cli/` 下，仓库根目录只保留元数据与便捷脚本。这样的结构更适合 agent 发现、按需加载和独立执行 skill。

## 关键 API / 配置
- 目录建议：
  - `skills/weibo-cli/SKILL.md`：skill 元数据与执行说明
  - `skills/weibo-cli/references/commands.md`：参数示例与使用场景
  - `skills/weibo-cli/scripts/weibo-cli`：稳定包装入口
  - `skills/weibo-cli/scripts/weibo_cli/cli.py`：根命令装配
  - `skills/weibo-cli/scripts/weibo_cli/service.py`：业务动作编排
  - `skills/weibo-cli/scripts/weibo_cli/api_client.py`：HTTP 封装、限流、错误归一
  - `skills/weibo-cli/scripts/weibo_cli/session.py`：登录态读取、校验、持久化
  - `skills/weibo-cli/scripts/weibo_cli/browser_login.py`：浏览器扫码登录
  - `skills/weibo-cli/scripts/weibo_cli/output.py`：终端文本格式化
  - `skills/weibo-cli/scripts/weibo_cli/skill_catalog.py`：skill 发现、展示、校验、XML 输出
  - `skills/weibo-cli/.venv/`：skill 本地虚拟环境
- package.json：
  - `bin.weibo-cli` 指向 `skills/weibo-cli/scripts/weibo-cli`
  - `npm run cli -- ...` 只是包装调用 skill 入口
  - `npm run skills:venv` 负责初始化 skill 本地依赖

## 注意事项
- `SKILL.md` frontmatter 是技能元数据唯一事实来源，不能再在另一套业务代码里手工维护重复 skill 清单。
- `scripts/weibo-cli` 必须优先能在 skill 目录语义下运行，不能假设用户当前位于仓库根目录。
- `.venv/`、`__pycache__/` 和 `*.pyc` 都属于运行产物，不应纳入版本控制。
- `.agent/run-snapshots/` 可保留历史快照，不作为当前活动架构事实来源。

## 来源
- 官方：Agent Skills 目录约定与前置信息实践
- 仓库当前实现：`skills/weibo-cli/` 目录结构与 wrapper 行为
- 官方：npm package.json `bin` 文档, https://docs.npmjs.com/cli/v11/configuring-npm/package-json/#bin

## 可信度：高
