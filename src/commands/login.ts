/** Responsibility: guide local QR login and persist acquired session state. */
import { Command } from "commander";
import qrcodeTerminal from "qrcode-terminal";
import readline from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";

import { persistSession } from "../auth/session.js";
import { getLocalConfigPath } from "../config/localConfig.js";

interface LoginOptions {
  cookie?: string;
  uid?: string;
  loginUrl: string;
  fromEnv?: boolean;
  prompt: boolean;
}

export function registerLoginCommand(program: Command): void {
  program
    .command("login")
    .description("通过本地扫码流程登录微博并保存登录态")
    .option("--cookie <cookie>", "直接写入已获取的微博 cookie")
    .option("--uid <uid>", "登录账号 UID，可选")
    .option(
      "--login-url <url>",
      "用于扫码的微博登录页 URL",
      "https://passport.weibo.com/signin/login?entry=mweibo&r=https%3A%2F%2Fm.weibo.cn%2F"
    )
    .option("--from-env", "从 WEIBO_COOKIE / WEIBO_UID 读取登录态并落本地")
    .option("--no-prompt", "不进入交互式输入；缺少 cookie 时直接失败")
    .action(async (options: LoginOptions) => {
      await handleLoginCommand(options);
    });
}

async function handleLoginCommand(options: LoginOptions): Promise<void> {
  const cookieFromArgs = options.cookie?.trim();
  const cookieFromEnv = options.fromEnv ? process.env.WEIBO_COOKIE?.trim() : undefined;
  const uidFromEnv = options.fromEnv ? process.env.WEIBO_UID?.trim() : undefined;

  if (!cookieFromArgs && !cookieFromEnv) {
    renderLoginInstructions(options.loginUrl);
  }

  const cookie = cookieFromArgs ?? cookieFromEnv ?? (options.prompt ? await promptForCookie() : undefined);
  const uid = options.uid?.trim() || uidFromEnv || (options.prompt ? await promptForUid() : undefined);

  if (!cookie) {
    throw new Error(
      `未提供可持久化的微博 cookie。请在扫码登录成功后重新执行 login，并通过 --cookie、--from-env 或交互式输入写入本地文件：${getLocalConfigPath()}`
    );
  }

  const { path, session } = await persistSession({
    cookie,
    uid,
    loginUrl: options.loginUrl
  });

  output.write(`登录态已写入 ${path}\n`);
  output.write(`来源：${cookieFromArgs || cookieFromEnv ? "显式提供" : "交互式录入"}\n`);
  output.write(`UID：${session.uid ?? "未提供"}\n`);
  output.write(`更新时间：${session.updatedAt}\n`);
}

function renderLoginInstructions(loginUrl: string): void {
  output.write("请使用微博 App 或手机浏览器扫描下方二维码，完成登录后再把当前浏览器 cookie 粘贴回终端。\n");
  output.write(`登录页：${loginUrl}\n\n`);
  qrcodeTerminal.generate(loginUrl, { small: true }, (qrcode) => {
    output.write(`${qrcode}\n`);
  });
  output.write("扫码完成后，可从已登录浏览器的开发者工具或应用 Cookie 面板复制整串 cookie。\n");
  output.write("也可以直接重新执行：WEIBO_COOKIE='你的cookie' npm run cli -- login --from-env\n\n");
}

async function promptForCookie(): Promise<string | undefined> {
  const rl = readline.createInterface({ input, output });

  try {
    const cookie = await rl.question("请输入登录成功后的完整 cookie：");
    return cookie.trim() || undefined;
  } finally {
    rl.close();
  }
}

async function promptForUid(): Promise<string | undefined> {
  const rl = readline.createInterface({ input, output });

  try {
    const uid = await rl.question("如已知账号 UID，请输入（可直接回车跳过）：");
    return uid.trim() || undefined;
  } finally {
    rl.close();
  }
}
