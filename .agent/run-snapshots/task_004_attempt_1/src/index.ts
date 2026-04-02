/** Responsibility: assemble the root CLI program and execute argument parsing. */
import { Command } from "commander";

import { registerListCommand } from "./commands/list.js";
import { registerLoginCommand } from "./commands/login.js";
import { registerPostCommand } from "./commands/post.js";
import { registerRepostsCommand } from "./commands/reposts.js";

export function createProgram(): Command {
  const program = new Command();

  program
    .name("weibo-cli")
    .description("面向个人账号的微博命令行工具")
    .showHelpAfterError()
    .version("0.1.0");

  registerLoginCommand(program);
  registerPostCommand(program);
  registerListCommand(program);
  registerRepostsCommand(program);

  return program;
}

export async function runCli(argv: string[]): Promise<void> {
  await createProgram().parseAsync(argv);
}
