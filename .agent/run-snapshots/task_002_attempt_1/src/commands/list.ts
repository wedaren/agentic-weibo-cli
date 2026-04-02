/** Responsibility: register the list command and expose listing options. */
import { Command } from "commander";

import { notImplemented } from "../output/messages.js";

export function registerListCommand(program: Command): void {
  program
    .command("list")
    .description("查看当前账号最近发布的微博")
    .option("--limit <number>", "返回微博条数", "10")
    .action(() => {
      notImplemented("list", "后续任务将接入微博列表查询服务。");
    });
}
