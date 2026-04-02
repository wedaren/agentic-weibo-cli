/** 职责：注册发微博命令，并在业务实现前先执行登录态预检查。 */
import { Command } from "commander";

import { assertSessionConfigured } from "../auth/session.js";
import { notImplemented } from "../output/messages.js";

export function registerPostCommand(program: Command): void {
  program
    .command("post")
    .description("发布一条微博")
    .requiredOption("--text <content>", "微博正文内容")
    .action(async () => {
      await assertSessionConfigured();
      notImplemented("post", "后续任务将接入登录态校验与发微博服务。");
    });
}
