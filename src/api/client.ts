/** 职责：封装微博 HTTP 请求、鉴权注入、基础限流与错误归一。 */
import { assertSessionConfigured, type WeiboSession } from "../auth/session.js";

export interface ApiClientOptions {
  session: WeiboSession;
  baseUrl?: string;
  minIntervalMs?: number;
  userAgent?: string;
  fetchImpl?: typeof fetch;
}

export interface RequestOptions extends Omit<RequestInit, "body" | "headers"> {
  query?: Record<string, string | number | boolean | undefined>;
  headers?: Record<string, string>;
  body?: BodyInit | URLSearchParams;
  authRequired?: boolean;
}

export interface SessionProbeResult {
  ok: boolean;
  url: string;
  login?: boolean;
  uid?: string;
}

interface WeiboConfigResponse {
  data?: {
    login?: boolean;
    uid?: string | number;
  };
}

export class WeiboApiError extends Error {
  public constructor(
    message: string,
    public readonly url: string,
    public readonly status?: number,
    public readonly details?: string
  ) {
    super(message);
    this.name = "WeiboApiError";
  }
}

export class WeiboAuthError extends WeiboApiError {
  public constructor(message: string, url: string, status?: number, details?: string) {
    super(message, url, status, details);
    this.name = "WeiboAuthError";
  }
}

export class WeiboApiClient {
  private readonly baseUrl: string;
  private readonly minIntervalMs: number;
  private readonly userAgent: string;
  private readonly fetchImpl: typeof fetch;
  private lastRequestAt = 0;

  public constructor(private readonly options: ApiClientOptions) {
    this.baseUrl = normalizeBaseUrl(options.baseUrl);
    this.minIntervalMs = Math.max(0, options.minIntervalMs ?? 250);
    this.userAgent =
      options.userAgent ??
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 weibo-cli/0.1.0";
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  public static async fromConfiguredSession(options: Omit<ApiClientOptions, "session"> = {}): Promise<WeiboApiClient> {
    const session = await assertSessionConfigured();
    return new WeiboApiClient({ ...options, session });
  }

  public getSession(): WeiboSession {
    return this.options.session;
  }

  public async validateSession(): Promise<SessionProbeResult> {
    const payload = await this.requestJson<WeiboConfigResponse>("/api/config", {
      method: "GET",
      authRequired: false
    });

    const login = payload.data?.login;
    const uid = normalizeUid(payload.data?.uid);

    if (login === false) {
      throw new WeiboAuthError("微博登录态已失效，请重新运行 login 更新 cookie。", this.buildUrl("/api/config"));
    }

    return {
      ok: true,
      url: this.buildUrl("/api/config"),
      login,
      uid
    };
  }

  public async requestJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const response = await this.request(path, options);
    const text = await response.text();

    if (!text.trim()) {
      return {} as T;
    }

    try {
      return JSON.parse(text) as T;
    } catch (error) {
      throw new WeiboApiError(
        `微博接口返回了非 JSON 响应，无法解析：${error instanceof Error ? error.message : "unknown parse error"}`,
        response.url,
        response.status,
        text.slice(0, 400)
      );
    }
  }

  public async request(path: string, options: RequestOptions = {}): Promise<Response> {
    await this.waitForRateLimit();

    const url = this.buildUrl(path, options.query);
    const response = await this.fetchImpl(url, {
      ...options,
      headers: this.buildHeaders(options.headers),
      body: options.body,
      redirect: options.redirect ?? "follow"
    });

    this.lastRequestAt = Date.now();

    if (response.status === 401 || response.status === 403) {
      const details = await response.text();
      throw new WeiboAuthError("微博登录态无效或已失效，请重新运行 login 更新 cookie。", response.url, response.status, details.slice(0, 400));
    }

    if (!response.ok) {
      const details = await response.text();
      throw new WeiboApiError(
        `微博接口请求失败（HTTP ${response.status}）。`,
        response.url,
        response.status,
        details.slice(0, 400)
      );
    }

    return response;
  }

  private buildHeaders(extraHeaders: Record<string, string> | undefined): Headers {
    const headers = new Headers(extraHeaders);
    const csrfToken = extractCookieValue(this.options.session.cookie, "XSRF-TOKEN") ?? extractCookieValue(this.options.session.cookie, "X-CSRF-TOKEN");

    if (!headers.has("accept")) {
      headers.set("accept", "application/json, text/plain, */*");
    }

    if (!headers.has("cookie")) {
      headers.set("cookie", this.options.session.cookie);
    }

    if (!headers.has("user-agent")) {
      headers.set("user-agent", this.userAgent);
    }

    if (csrfToken && !headers.has("x-xsrf-token")) {
      headers.set("x-xsrf-token", csrfToken);
    }

    if (csrfToken && !headers.has("x-csrf-token")) {
      headers.set("x-csrf-token", csrfToken);
    }

    return headers;
  }

  private buildUrl(path: string, query?: Record<string, string | number | boolean | undefined>): string {
    const url = new URL(path, this.baseUrl);

    for (const [key, value] of Object.entries(query ?? {})) {
      if (value === undefined) {
        continue;
      }

      url.searchParams.set(key, String(value));
    }

    return url.toString();
  }

  private async waitForRateLimit(): Promise<void> {
    const waitMs = this.lastRequestAt + this.minIntervalMs - Date.now();

    if (waitMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, waitMs));
    }
  }
}

function normalizeBaseUrl(baseUrl: string | undefined): string {
  const resolved = baseUrl?.trim() || process.env.WEIBO_API_BASE_URL?.trim() || "https://m.weibo.cn";
  return resolved.endsWith("/") ? resolved : `${resolved}/`;
}

function normalizeUid(uid: string | number | undefined): string | undefined {
  if (uid === undefined || uid === null) {
    return undefined;
  }

  return String(uid).trim() || undefined;
}

function extractCookieValue(cookieHeader: string, key: string): string | undefined {
  const escapedKey = key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = cookieHeader.match(new RegExp(`(?:^|;\\s*)${escapedKey}=([^;]+)`));
  return match?.[1];
}
