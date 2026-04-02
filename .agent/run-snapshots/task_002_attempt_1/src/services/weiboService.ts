/** Responsibility: define the service-layer contract for Weibo business actions. */
import { WeiboApiClient } from "../api/client.js";

export class WeiboService {
  public constructor(private readonly client: WeiboApiClient) {}

  public getClient(): WeiboApiClient {
    return this.client;
  }
}
