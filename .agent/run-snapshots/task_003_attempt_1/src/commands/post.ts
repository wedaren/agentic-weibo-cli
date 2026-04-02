/** Responsibility: register the post command and validate its primary input shape. */
import { Command } from "commander";

import { notImplemented } from "../output/messages.js";

export function registerPostCommand(program: Command): void {
  program
    .command("post")
    .description("发布一条微博")
    .requiredOption("--text <content>", "微博正文内容")
    .action(() => {
      notImplemented("post", "后续任务将接入登录态校验与发微博服务。");
    });
}
