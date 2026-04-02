/** Responsibility: register the login command and provide MVP placeholder guidance. */
import { Command } from "commander";

import { notImplemented } from "../output/messages.js";

export function registerLoginCommand(program: Command): void {
  program
    .command("login")
    .description("通过本地扫码流程登录微博并保存登录态")
    .action(() => {
      notImplemented("login", "后续任务将接入本地扫码登录与登录态持久化。");
    });
}
