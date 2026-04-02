/** 职责：注册转发查询命令，并调用微博服务层查询指定微博的转发信息。 */
import { Command } from "commander";

import { formatReposts } from "../output/weibo.js";
import { WeiboService } from "../services/weiboService.js";

interface RepostsCommandOptions {
  weiboId: string;
  limit: string;
  page: string;
}

export function registerRepostsCommand(program: Command): void {
  program
    .command("reposts")
    .description("获取指定微博的转发信息")
    .requiredOption("--weibo-id <id>", "微博 ID")
    .option("--limit <number>", "返回转发条数", "20")
    .option("--page <number>", "页码", "1")
    .action(async (options: RepostsCommandOptions) => {
      const service = await WeiboService.createDefault();
      const items = await service.getReposts({
        weiboId: options.weiboId,
        limit: parsePositiveIntegerOption(options.limit, "--limit"),
        page: parsePositiveIntegerOption(options.page, "--page")
      });
      process.stdout.write(formatReposts(items));
    });
}

function parsePositiveIntegerOption(value: string, optionName: string): number {
  const parsed = Number.parseInt(value, 10);

  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`${optionName} 必须是大于 0 的整数。`);
  }

  return parsed;
}
