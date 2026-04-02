/** Responsibility: load, validate, and persist Weibo session state for CLI commands. */
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
  const session = await loadSession();

  if (!session) {
    throw new Error(
      `微博登录态尚未配置。请先运行 login，或通过环境变量 WEIBO_COOKIE/WEIBO_UID 提供登录态。默认本地文件路径：${getLocalConfigPath()}`
    );
  }

  return session;
}

export function looksLikeCookie(cookie: string): boolean {
  return cookie.includes("=") && cookie.includes(";");
}

function normalizeCookie(value: string | undefined): string | null {
  const normalized = value?.trim();
  return normalized && looksLikeCookie(normalized) ? normalized : null;
}

function normalizeOptionalField(value: string | undefined): string | undefined {
  const normalized = value?.trim();
  return normalized ? normalized : undefined;
}
