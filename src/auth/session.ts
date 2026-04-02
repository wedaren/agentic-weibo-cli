/** 职责：加载、校验并持久化微博登录态，供 CLI 和 API 客户端复用。 */
import {
  getLocalConfigPath,
  readLocalConfig,
  writeLocalConfig,
  type LocalConfig
} from "../config/localConfig.js";

export interface WeiboSession {
  cookie: string;
  uid?: string;
  loginUrl?: string;
  updatedAt: string;
  source: "env" | "local";
}

export interface PersistedSessionInput {
  cookie: string;
  uid?: string;
  loginUrl?: string;
}

export interface SessionValidationSummary {
  authCookieKeys: string[];
  missingAuthCookieKeys: string[];
  expiresAt?: string;
}

const AUTH_COOKIE_KEYS = ["SUB", "SUBP", "SCF"] as const;
const EXPIRY_COOKIE_KEY = "ALF";

export async function loadSession(): Promise<WeiboSession | null> {
  const envCookie = normalizeCookie(process.env.WEIBO_COOKIE);
  const envUid = normalizeOptionalField(process.env.WEIBO_UID);

  if (envCookie) {
    return {
      cookie: envCookie,
      uid: envUid,
      updatedAt: new Date().toISOString(),
      source: "env"
    };
  }

  const localConfig = await readLocalConfig();
  const localCookie = normalizeCookie(localConfig?.cookie);

  if (!localCookie) {
    return null;
  }

  return {
    cookie: localCookie,
    uid: normalizeOptionalField(localConfig?.uid),
    loginUrl: normalizeOptionalField(localConfig?.loginUrl),
    updatedAt: normalizeOptionalField(localConfig?.updatedAt) ?? new Date().toISOString(),
    source: "local"
  };
}

export async function persistSession(input: PersistedSessionInput): Promise<{ path: string; session: WeiboSession }> {
  const cookie = normalizeCookie(input.cookie);

  if (!cookie) {
    throw new Error("微博 cookie 为空。请在扫码登录成功后粘贴浏览器中的完整 cookie 字符串。");
  }

  const localConfig: LocalConfig = {
    cookie,
    uid: normalizeOptionalField(input.uid),
    loginUrl: normalizeOptionalField(input.loginUrl),
    updatedAt: new Date().toISOString()
  };

  const path = await writeLocalConfig(localConfig);

  return {
    path,
    session: {
      cookie,
      uid: localConfig.uid,
      loginUrl: localConfig.loginUrl,
      updatedAt: localConfig.updatedAt ?? new Date().toISOString(),
      source: "local"
    }
  };
}

export async function assertSessionConfigured(): Promise<WeiboSession> {
  assertRawCookieShape("环境变量 WEIBO_COOKIE", process.env.WEIBO_COOKIE);

  const localConfig = await readLocalConfig();
  assertRawCookieShape(`本地登录态文件 ${getLocalConfigPath()}`, localConfig?.cookie);

  const session = await loadSession();

  if (!session) {
    throw new Error(
      `微博登录态尚未配置。请先运行 login，或通过环境变量 WEIBO_COOKIE/WEIBO_UID 提供登录态。默认本地文件路径：${getLocalConfigPath()}`
    );
  }

  return validateSession(session);
}

export function validateSession(session: WeiboSession): WeiboSession {
  const normalizedCookie = normalizeCookie(session.cookie);

  if (!normalizedCookie) {
    throw new Error("微博登录态格式无效。cookie 必须是浏览器导出的完整请求头字符串，例如 `name=value; other=value`。");
  }

  const summary = summarizeSession(normalizedCookie);

  if (summary.authCookieKeys.length === 0) {
    throw new Error(
      `微博登录态缺少核心鉴权 cookie。至少需要包含 ${AUTH_COOKIE_KEYS.join("/") } 之一，请重新执行 login 或从已登录浏览器复制完整 cookie。`
    );
  }

  if (summary.expiresAt && Date.parse(summary.expiresAt) <= Date.now()) {
    throw new Error(`微博登录态已过期（ALF=${summary.expiresAt}）。请重新运行 login 更新本地登录态。`);
  }

  return {
    ...session,
    cookie: normalizedCookie,
    uid: normalizeOptionalField(session.uid),
    loginUrl: normalizeOptionalField(session.loginUrl),
    updatedAt: normalizeOptionalField(session.updatedAt) ?? new Date().toISOString()
  };
}

export function looksLikeCookie(cookie: string): boolean {
  return cookie.includes("=") && cookie.includes(";");
}

export function summarizeSession(cookie: string): SessionValidationSummary {
  const cookies = parseCookieHeader(cookie);
  const authCookieKeys = AUTH_COOKIE_KEYS.filter((key) => cookies.has(key));
  const missingAuthCookieKeys = AUTH_COOKIE_KEYS.filter((key) => !cookies.has(key));
  const expiresAt = readCookieExpiry(cookies.get(EXPIRY_COOKIE_KEY));

  return {
    authCookieKeys: [...authCookieKeys],
    missingAuthCookieKeys: [...missingAuthCookieKeys],
    expiresAt
  };
}

export function parseCookieHeader(cookie: string): Map<string, string> {
  const entries = cookie
    .split(";")
    .map((segment) => segment.trim())
    .filter((segment) => segment.length > 0)
    .map((segment) => {
      const separatorIndex = segment.indexOf("=");

      if (separatorIndex <= 0) {
        return null;
      }

      return [
        segment.slice(0, separatorIndex).trim(),
        segment.slice(separatorIndex + 1).trim()
      ] as const;
    })
    .filter((entry): entry is readonly [string, string] => entry !== null && entry[0].length > 0);

  return new Map(entries);
}

function normalizeCookie(value: string | undefined): string | null {
  const normalized = value?.trim();
  return normalized && looksLikeCookie(normalized) ? normalized : null;
}

function normalizeOptionalField(value: string | undefined): string | undefined {
  const normalized = value?.trim();
  return normalized ? normalized : undefined;
}

function assertRawCookieShape(sourceLabel: string, value: string | undefined): void {
  const normalized = normalizeOptionalField(value);

  if (!normalized) {
    return;
  }

  if (!looksLikeCookie(normalized)) {
    throw new Error(`${sourceLabel} 格式无效。cookie 至少应包含一个分号分隔的键值对，例如 \`SUB=...; SUBP=...\`。`);
  }
}

function readCookieExpiry(rawExpiry: string | undefined): string | undefined {
  if (!rawExpiry) {
    return undefined;
  }

  const seconds = Number(rawExpiry);

  if (!Number.isFinite(seconds) || seconds <= 0) {
    return undefined;
  }

  return new Date(seconds * 1000).toISOString();
}
