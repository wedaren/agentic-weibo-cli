/** Responsibility: acquire Weibo session via browser QR login or explicit cookie input. */
import { Command } from "commander";
import qrcodeTerminal from "qrcode-terminal";
import readline from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";

import { WeiboApiClient } from "../api/client.js";
import { assertBrowserAutomationAvailable, runBrowserLogin } from "../auth/browserLogin.js";
import { persistSession } from "../auth/session.js";
import { getLocalConfigPath } from "../config/localConfig.js";

interface LoginOptions {
  cookie?: string;
  uid?: string;
  loginUrl: string;
  browserPath?: string;
  timeoutSec: string;
  manual?: boolean;
  checkBrowser?: boolean;
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
      "https://passport.weibo.com/sso/signin?entry=wapsso&source=wapssowb&url=https%3A%2F%2Fweibo.com"
    )
    .option("--browser-path <path>", "指定本地 Chrome/Chromium 可执行文件路径")
    .option("--timeout-sec <number>", "等待扫码登录成功的超时时间（秒）", "180")
    .option("--manual", "使用手动模式：显示二维码后自行粘贴 cookie")
    .option("--check-browser", "仅检查浏览器自动化依赖是否可用，然后退出")
    .option("--from-env", "从 WEIBO_COOKIE / WEIBO_UID 读取登录态并落本地")
    .option("--no-prompt", "不进入交互式输入；缺少 cookie 时直接失败")
    .action(async (options: LoginOptions) => {
      await handleLoginCommand(options);
    });
}

async function handleLoginCommand(options: LoginOptions): Promise<void> {
  const timeoutMs = parseTimeoutMs(options.timeoutSec);
  const cookieFromArgs = options.cookie?.trim();
  const cookieFromEnv = options.fromEnv ? process.env.WEIBO_COOKIE?.trim() : undefined;
  const uidFromEnv = options.fromEnv ? process.env.WEIBO_UID?.trim() : undefined;

  if (options.checkBrowser) {
    const executablePath = await assertBrowserAutomationAvailable(options.browserPath);
    output.write(`浏览器自动化可用：${executablePath}\n`);
    return;
  }

  let cookie = cookieFromArgs ?? cookieFromEnv;
  let uid = options.uid?.trim() || uidFromEnv;
  let sourceLabel = cookieFromArgs || cookieFromEnv ? "显式提供" : "浏览器扫码";
  let browserDiagnostics = "";

  if (!cookie && !options.manual) {
    renderBrowserLoginInstructions(options.loginUrl, timeoutMs);
    try {
      const browserLogin = await runBrowserLogin({
        loginUrl: options.loginUrl,
        browserPath: options.browserPath,
        timeoutMs
      });
      cookie = browserLogin.cookie;
      uid = uid ?? browserLogin.uid;
      browserDiagnostics = `最终页面：${browserLogin.finalUrl ?? options.loginUrl}\n捕获到的 cookie 键：${browserLogin.cookieKeys.join(", ")}\n`;
    } catch (error) {
      const message = error instanceof Error ? error.message : "未知浏览器自动化错误";
      output.write(`浏览器扫码登录不可用，已降级到手动模式：${message}\n\n`);
    }
  }

  if (!cookie) {
    renderManualLoginInstructions(options.loginUrl);
    cookie = options.prompt ? await promptForCookie() : undefined;
    uid = uid ?? (options.prompt ? await promptForUid() : undefined);
    sourceLabel = "手动录入";
  }

  if (!cookie) {
    throw new Error(
      `未提供可持久化的微博 cookie。请在扫码登录成功后重新执行 login，并通过浏览器扫码、--cookie、--from-env 或手动模式写入本地文件：${getLocalConfigPath()}`
    );
  }

  const validatedSession = await validateSessionBeforePersist(cookie, uid);
  uid = validatedSession.uid ?? uid;

  const { path, session } = await persistSession({
    cookie,
    uid,
    loginUrl: options.loginUrl
  });

  output.write(`登录态已写入 ${path}\n`);
  output.write(`来源：${sourceLabel}\n`);
  output.write(`UID：${session.uid ?? "未提供"}\n`);
  output.write(`更新时间：${session.updatedAt}\n`);
  if (browserDiagnostics) {
    output.write(browserDiagnostics);
  }
}

function renderBrowserLoginInstructions(loginUrl: string, timeoutMs: number): void {
  output.write("即将自动打开本地浏览器，请在浏览器里完成微博扫码登录。\n");
  output.write(`登录页：${loginUrl}\n`);
  output.write(`等待时间：${Math.round(timeoutMs / 1000)} 秒\n\n`);
}

function renderManualLoginInstructions(loginUrl: string): void {
  output.write("当前使用手动模式。请使用微博 App 或手机浏览器扫描下方二维码，完成登录后再把当前浏览器 cookie 粘贴回终端。\n");
  output.write(`登录页：${loginUrl}\n\n`);
  qrcodeTerminal.generate(loginUrl, { small: true }, (qrcode) => {
    output.write(`${qrcode}\n`);
  });
  output.write("扫码完成后，可从已登录浏览器的开发者工具或应用 Cookie 面板复制整串 cookie。\n");
  output.write("也可以直接重新执行：WEIBO_COOKIE='你的cookie' npm run cli -- login --from-env\n\n");
}

function parseTimeoutMs(rawValue: string): number {
  const seconds = Number.parseInt(rawValue, 10);

  if (!Number.isInteger(seconds) || seconds <= 0) {
    throw new Error("--timeout-sec 必须是大于 0 的整数。");
  }

  return seconds * 1000;
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

async function validateSessionBeforePersist(cookie: string, uid?: string): Promise<{ uid?: string }> {
  const client = new WeiboApiClient({
    session: {
      cookie,
      uid,
      updatedAt: new Date().toISOString(),
      source: "local"
    }
  });

  try {
    const result = await client.validateSession();

    if (result.login === false) {
      throw new Error("微博业务接口确认当前 cookie 未登录。");
    }

    return {
      uid: result.uid ?? uid
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : "未知验证错误";
    throw new Error(`获取到的 cookie 尚未通过微博业务接口校验，请重新登录。详细原因：${message}`);
  }
}
