/** 职责：通过本地浏览器扫码登录微博，并自动提取可持久化的登录态。 */
import { access, mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { chromium, type Page } from "playwright";

import { WeiboApiClient } from "../api/client.js";
import { getLocalDataDir } from "../config/localConfig.js";

const DEFAULT_LOGIN_URL =
  "https://passport.weibo.com/sso/signin?entry=wapsso&source=wapssowb&url=https%3A%2F%2Fweibo.com";
const AUTH_COOKIE_KEYS = ["SUB", "SUBP", "SCF"] as const;
const BUSINESS_ORIGINS = ["https://weibo.com", "https://m.weibo.cn"] as const;
const DOMAIN_PRIORITY = ["m.weibo.cn", ".m.weibo.cn", "weibo.com", ".weibo.com", "passport.weibo.com", ".passport.weibo.com"] as const;

export interface BrowserLoginOptions {
  loginUrl?: string;
  browserPath?: string;
  timeoutMs?: number;
  pollIntervalMs?: number;
  headless?: boolean;
}

export interface BrowserLoginResult {
  cookie: string;
  uid?: string;
  loginUrl: string;
  finalUrl?: string;
  cookieKeys: string[];
}

export async function runBrowserLogin(options: BrowserLoginOptions = {}): Promise<BrowserLoginResult> {
  const executablePath = await findBrowserExecutable(options.browserPath);
  const loginUrl = options.loginUrl?.trim() || DEFAULT_LOGIN_URL;
  const timeoutMs = Math.max(15_000, options.timeoutMs ?? 180_000);
  const pollIntervalMs = Math.max(1_000, options.pollIntervalMs ?? 2_000);
  const profileDir = await mkdtemp(path.join(os.tmpdir(), "weibo-cli-login-"));

  let context:
    | Awaited<ReturnType<typeof chromium.launchPersistentContext>>
    | undefined;

  try {
    context = await chromium.launchPersistentContext(profileDir, {
      executablePath,
      headless: options.headless ?? false,
      viewport: null
    });

    const page = context.pages()[0] ?? (await context.newPage());
    await page.goto(loginUrl, { waitUntil: "domcontentloaded" });

    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const currentUrl = page.url();
      const onBusinessDomain = isBusinessUrl(currentUrl);

      if (onBusinessDomain) {
        await hydrateBusinessCookies(page).catch(() => undefined);
      }

      const extracted = await extractCookieHeader(context);

      if (extracted) {
        const refreshed = (await extractCookieHeader(context)) ?? extracted;
        const pageUrl = page.url();
        const probe = await probeUid(refreshed.cookie).catch(() => undefined);

        if (onBusinessDomain && (probe?.uid || probe?.login !== false)) {
          return {
            cookie: refreshed.cookie,
            uid: probe?.uid,
            loginUrl,
            finalUrl: pageUrl,
            cookieKeys: refreshed.cookieKeys
          };
        }
      }

      await page.waitForTimeout(pollIntervalMs);
    }

    throw new Error(
      `等待扫码登录超时（${Math.round(timeoutMs / 1000)} 秒）。请确认你已在浏览器中完成微博登录，或使用 --manual 手动模式写入 cookie。`
    );
  } finally {
    await context?.close().catch(() => undefined);
    await rm(profileDir, { recursive: true, force: true }).catch(() => undefined);
  }
}

function isBusinessUrl(url: string): boolean {
  return BUSINESS_ORIGINS.some((origin) => url.startsWith(origin));
}

async function hydrateBusinessCookies(page: Page): Promise<void> {
  for (const targetUrl of BUSINESS_ORIGINS) {
    await page.goto(targetUrl, {
      waitUntil: "domcontentloaded",
      timeout: 15_000
    });
  }
}

export async function assertBrowserAutomationAvailable(browserPath?: string): Promise<string> {
  const executablePath = await findBrowserExecutable(browserPath);
  const browser = await chromium.launch({
    executablePath,
    headless: true
  });
  await browser.close();
  return executablePath;
}

export async function findBrowserExecutable(browserPath?: string): Promise<string> {
  const candidates = [
    browserPath?.trim(),
    process.env.WEIBO_CHROME_PATH?.trim(),
    process.platform === "darwin" ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" : undefined,
    process.platform === "darwin" ? "/Applications/Chromium.app/Contents/MacOS/Chromium" : undefined,
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser"
  ].filter((value): value is string => Boolean(value));

  for (const candidate of candidates) {
    try {
      await access(candidate);
      return candidate;
    } catch {
      continue;
    }
  }

  throw new Error(
    `未找到可用的 Chrome/Chromium 浏览器。请安装 Google Chrome，或通过 --browser-path / WEIBO_CHROME_PATH 指定浏览器路径。默认数据目录：${getLocalDataDir()}`
  );
}

async function extractCookieHeader(
  context: Awaited<ReturnType<typeof chromium.launchPersistentContext>>
): Promise<{ cookie: string; cookieKeys: string[] } | undefined> {
  const cookies = await context.cookies([
    "https://m.weibo.cn",
    "https://weibo.com",
    "https://passport.weibo.com"
  ]);

  const relevantCookies = dedupeCookies(
    cookies.filter((cookie) => cookie.domain.includes("weibo"))
  ).map((cookie) => `${cookie.name}=${cookie.value}`);

  if (!AUTH_COOKIE_KEYS.some((key) => relevantCookies.some((entry) => entry.startsWith(`${key}=`)))) {
    return undefined;
  }

  return {
    cookie: relevantCookies.join("; "),
    cookieKeys: relevantCookies.map((entry) => entry.split("=", 1)[0]).sort()
  };
}

function dedupeCookies(
  cookies: Array<{
    name: string;
    value: string;
    domain: string;
    path: string;
    expires: number;
  }>
): Array<{
  name: string;
  value: string;
  domain: string;
  path: string;
  expires: number;
}> {
  const selected = new Map<string, (typeof cookies)[number]>();

  for (const cookie of cookies) {
    const current = selected.get(cookie.name);

    if (!current || compareCookiePriority(cookie, current) > 0) {
      selected.set(cookie.name, cookie);
    }
  }

  return [...selected.values()].sort((left, right) => left.name.localeCompare(right.name));
}

function compareCookiePriority(
  candidate: { domain: string; path: string; expires: number },
  current: { domain: string; path: string; expires: number }
): number {
  const domainScore = scoreDomain(candidate.domain) - scoreDomain(current.domain);

  if (domainScore !== 0) {
    return domainScore;
  }

  const pathScore = candidate.path.length - current.path.length;
  if (pathScore !== 0) {
    return pathScore;
  }

  return candidate.expires - current.expires;
}

function scoreDomain(domain: string): number {
  const index = DOMAIN_PRIORITY.findIndex((value) => value === domain);
  return index === -1 ? 0 : DOMAIN_PRIORITY.length - index;
}

async function probeUid(cookie: string): Promise<{ uid?: string; login?: boolean }> {
  const client = new WeiboApiClient({
    session: {
      cookie,
      updatedAt: new Date().toISOString(),
      source: "local"
    }
  });
  const result = await client.validateSession();
  return {
    uid: result.uid,
    login: result.login
  };
}
