/** 职责：注册转发查询命令，并在业务实现前先执行登录态预检查。 */
import { Command } from "commander";

import { assertSessionConfigured } from "../auth/session.js";
import { notImplemented } from "../output/messages.js";

export function registerRepostsCommand(program: Command): void {
  program
    .command("reposts")
    .description("获取指定微博的转发信息")
    .requiredOption("--weibo-id <id>", "微博 ID")
    .option("--limit <number>", "返回转发条数", "20")
    .action(async () => {
      await assertSessionConfigured();
      notImplemented("reposts", "后续任务将接入转发信息查询服务。");
    });
}
