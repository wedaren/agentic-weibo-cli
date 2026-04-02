/** 职责：注册微博列表命令，并在业务实现前先执行登录态预检查。 */
import { Command } from "commander";

import { assertSessionConfigured } from "../auth/session.js";
import { notImplemented } from "../output/messages.js";

export function registerListCommand(program: Command): void {
  program
    .command("list")
    .description("查看当前账号最近发布的微博")
    .option("--limit <number>", "返回微博条数", "10")
    .action(async () => {
      await assertSessionConfigured();
      notImplemented("list", "后续任务将接入微博列表查询服务。");
    });
}
