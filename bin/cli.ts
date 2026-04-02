#!/usr/bin/env node
/** 职责：作为进程入口启动 CLI，并输出稳定的中文错误信息。 */
import { runCli } from "../src/index.js";

void runCli(process.argv).catch((error: unknown) => {
  const message = error instanceof Error ? error.message : "未知错误";
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
});
