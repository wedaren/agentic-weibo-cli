## 结论（3 句话以内）
项目结构应按 CLI 入口、命令层、服务层、API 客户端、认证层、配置层、输出层拆分，避免把鉴权和业务逻辑塞进命令文件。TypeScript 编译产物固定输出到 `dist/`，源码集中在 `src/`，CLI 二进制入口放 `bin/`。模块解析优先按 Node 语义配置，保证后续 ESM/CJS 边界和 npm script 运行稳定。

## 关键 API / 配置
- 目录建议：
  - `bin/cli.ts` 或 `bin/cli.js`：可执行入口
  - `src/index.ts`：装配根命令
  - `src/commands/*.ts`：`login`、`post`、`list`、`reposts`
  - `src/services/weiboService.ts`：业务动作编排
  - `src/api/client.ts`：HTTP 封装、重试、限流、错误归一
  - `src/auth/session.ts`：登录态读取、校验、注入
  - `src/config/*.ts`：环境变量与本地配置读取
  - `src/output/*.ts`：表格/文本格式化
- TypeScript：
  - `rootDir` 指向 `src`（或仓库根配合 `bin`），`outDir` 指向 `dist`
  - `moduleResolution` 采用 `nodenext` 或与 Node 版本一致的 node 模式
  - 开启 `strict`，并用 `resolveJsonModule` 支撑本地 JSON 配置读取
- npm：
  - `bin` 映射到最终 CLI 文件
  - `npm run help` 可以直接调用编译后或运行时入口输出帮助

## 注意事项
- `rootDir` 只影响输出目录结构，不决定编译包含关系；`include`/`exclude` 仍需单独配置。
- `bin` 与 `directories.bin` 不能同时使用，MVP 只保留单一 CLI 入口即可。
- 若源码同时包含 `src/` 与 `bin/`，要么把 `rootDir` 提升到项目根，要么通过单独构建步骤复制可执行入口。

## 来源
- 官方：TypeScript TSConfig `rootDir`, https://www.typescriptlang.org/tsconfig/#rootDir
- 官方：TypeScript TSConfig `moduleResolution`, https://www.typescriptlang.org/tsconfig/#moduleResolution
- 官方：npm package.json `bin` 文档, https://docs.npmjs.com/cli/v11/configuring-npm/package-json/#bin

## 可信度：高
