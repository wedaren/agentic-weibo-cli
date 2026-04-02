## 任务：task_004 第1次
## 从历史学到：现有链路已经把 session 校验和 API client 打通，这次应直接把 post/list/reposts 落到服务层和命令层，而不是再改 CLI 骨架
## 用到的 knowledge：core-tech-stack.md、project-structure.md、key-integrations.md
## 本次假设（与上次核心区别）：沿用 m.weibo.cn cookie 注入客户端，并把发微博、个人时间线、转发时间线三个动作集中到服务层，就能在不引入新依赖的前提下完成 task_004
## 实现摘要：实现微博服务层的 post/list/reposts 三个业务动作，接入 m.weibo.cn 的更新、个人列表和转发查询接口；三个 CLI 命令改为真实调用服务层并补充分页/数值校验；新增终端输出格式化模块，保留未登录时的清晰失败提示
## 自评分：94/100
## 各维度：核心34/40 | 编译25/25 | 选型20/20 | 约束15/15
## 下次改进方向：补一轮带真实登录态的联调，确认时间线和发微博接口在当前 cookie/风控条件下的返回字段没有漂移
