/** 职责：注册发微博命令，并调用微博服务层执行发布。 */
import { Command } from "commander";

import { formatPostResult } from "../output/weibo.js";
import { WeiboService } from "../services/weiboService.js";

interface PostCommandOptions {
  text: string;
}

export function registerPostCommand(program: Command): void {
  program
    .command("post")
    .description("发布一条微博")
    .requiredOption("--text <content>", "微博正文内容")
    .action(async (options: PostCommandOptions) => {
      const service = await WeiboService.createDefault();
      const result = await service.postWeibo({ text: options.text });
      process.stdout.write(formatPostResult(result));
    });
}
