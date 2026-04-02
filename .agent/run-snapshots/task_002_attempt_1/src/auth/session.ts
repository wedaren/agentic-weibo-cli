/** Responsibility: provide the session shape used by authentication and API layers. */
export interface WeiboSession {
  cookie: string;
  uid?: string;
}

export function assertSessionConfigured(): never {
  throw new Error("微博登录态尚未配置。请先运行 login 或通过本地配置提供 cookie。");
}
