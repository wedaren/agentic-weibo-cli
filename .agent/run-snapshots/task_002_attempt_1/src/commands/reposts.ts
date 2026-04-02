/** Responsibility: register the reposts command and capture lookup arguments. */
import { Command } from "commander";

import { notImplemented } from "../output/messages.js";

export function registerRepostsCommand(program: Command): void {
  program
    .command("reposts")
    .description("获取指定微博的转发信息")
    .requiredOption("--weibo-id <id>", "微博 ID")
    .option("--limit <number>", "返回转发条数", "20")
    .action(() => {
      notImplemented("reposts", "后续任务将接入转发信息查询服务。");
    });
}
