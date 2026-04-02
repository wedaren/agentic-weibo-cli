/** 职责：承接微博业务动作，并统一拿到已配置的 API 客户端。 */
import { WeiboApiClient } from "../api/client.js";

export class WeiboService {
  public constructor(private readonly client: WeiboApiClient) {}

  public static async createDefault(): Promise<WeiboService> {
    const client = await WeiboApiClient.fromConfiguredSession();
    return new WeiboService(client);
  }

  public getClient(): WeiboApiClient {
    return this.client;
  }
}
