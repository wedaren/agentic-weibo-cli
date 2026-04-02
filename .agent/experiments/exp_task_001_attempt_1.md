## 任务：task_001 第1次
## 从历史学到：当前没有失败实验记录，这次需要一次性把分层骨架、构建链路和命令帮助入口搭完整
## 用到的 knowledge：core-tech-stack.md、project-structure.md、key-integrations.md
## 本次假设（与上次核心区别）：以 Commander + TypeScript 最小可运行骨架先完成命令发现、编译和帮助输出，再为后续登录/服务层预留稳定目录
## 实现摘要：新增 package.json、tsconfig.json、bin/cli.ts、src 分层目录与四个基础命令；补充认证/API/配置/服务占位模块；验证 npm run build 与 npm run help 成功
## 自评分：96/100
## 各维度：核心36/40 | 编译25/25 | 选型20/20 | 约束15/15
## 下次改进方向：在 task_002 接入本地扫码登录流程与本地登录态持久化，并保持现有命令层接口稳定
