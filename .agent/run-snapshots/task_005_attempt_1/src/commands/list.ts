/** 职责：注册个人微博列表命令，并调用微博服务层查询结果。 */
import { Command } from "commander";

import { formatWeiboList } from "../output/weibo.js";
import { WeiboService } from "../services/weiboService.js";

interface ListCommandOptions {
  limit: string;
  page: string;
}

export function registerListCommand(program: Command): void {
  program
    .command("list")
    .description("查看当前账号最近发布的微博")
    .option("--limit <number>", "返回微博条数", "10")
    .option("--page <number>", "页码", "1")
    .action(async (options: ListCommandOptions) => {
      const service = await WeiboService.createDefault();
      const items = await service.listOwnWeibos({
        limit: parsePositiveIntegerOption(options.limit, "--limit"),
        page: parsePositiveIntegerOption(options.page, "--page")
      });
      process.stdout.write(formatWeiboList(items));
    });
}

function parsePositiveIntegerOption(value: string, optionName: string): number {
  const parsed = Number.parseInt(value, 10);

  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`${optionName} 必须是大于 0 的整数。`);
  }

  return parsed;
}
