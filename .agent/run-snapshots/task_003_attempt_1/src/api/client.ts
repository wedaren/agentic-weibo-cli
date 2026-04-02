/** Responsibility: declare the API client boundary used by services. */
import type { WeiboSession } from "../auth/session.js";

export interface ApiClientOptions {
  session: WeiboSession;
}

export class WeiboApiClient {
  public constructor(private readonly options: ApiClientOptions) {}

  public getSession(): WeiboSession {
    return this.options.session;
  }
}
