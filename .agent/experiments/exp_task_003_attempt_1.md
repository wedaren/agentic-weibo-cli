## 任务：task_003 第1次
## 从历史学到：现有 CLI 骨架和登录持久化已经稳定，这次应补齐“加载 session -> 校验 -> 注入 API client”的链路，而不是改命令结构
## 用到的 knowledge：core-tech-stack.md、project-structure.md、key-integrations.md
## 本次假设（与上次核心区别）：在不引入额外依赖的前提下，把登录态格式校验、过期判断、Cookie 注入、统一错误处理和基础请求封装一次补齐，就能为后续 post/list/reposts 服务层提供稳定底座
## 实现摘要：增强 session 模块，支持环境变量/本地文件登录态的来源感知校验、核心鉴权 cookie 检查和 ALF 过期判断；实现 API 客户端的请求封装、Cookie 注入、基础限流、鉴权错误归一和 session 探活；调整 CLI 入口和占位命令，使未配置或失效登录态能快速返回明确中文错误
## 自评分：96/100
## 各维度：核心36/40 | 编译25/25 | 选型20/20 | 约束15/15
## 下次改进方向：在 task_004 结合真实微博接口把 validateSession 与 post/list/reposts 调通，并补充接口失败场景的更细粒度错误映射
