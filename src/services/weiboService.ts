/** 职责：封装微博发布、列表查询和转发查询等业务动作。 */
import { WeiboApiClient } from "../api/client.js";

export interface PostWeiboInput {
  text: string;
}

export interface PostWeiboResult {
  id: string;
  bid?: string;
  createdAt?: string;
  text: string;
  url?: string;
}

export interface ListWeiboInput {
  limit: number;
  page: number;
}

export interface ListWeiboItem {
  id: string;
  bid?: string;
  createdAt?: string;
  text: string;
  source?: string;
  repostsCount?: number;
  commentsCount?: number;
  attitudesCount?: number;
}

export interface RepostsQueryInput {
  weiboId: string;
  limit: number;
  page: number;
}

export interface RepostItem {
  id: string;
  createdAt?: string;
  text: string;
  source?: string;
  userName?: string;
  userId?: string;
}

interface WeiboApiEnvelope<T> {
  ok?: number;
  msg?: string;
  message?: string;
  data?: T;
}

interface TimelineData {
  cards?: Array<{
    card_type?: number;
    mblog?: RawMblog;
  }>;
}

interface RepostsData {
  data?: RawMblog[];
  list?: RawMblog[];
}

interface RawMblog {
  id?: string | number;
  bid?: string;
  created_at?: string;
  text?: string;
  source?: string;
  reposts_count?: number;
  comments_count?: number;
  attitudes_count?: number;
  user?: {
    id?: string | number;
    screen_name?: string;
  };
}

export class WeiboService {
  private resolvedUid?: string;

  public constructor(private readonly client: WeiboApiClient) {}

  public static async createDefault(): Promise<WeiboService> {
    const client = await WeiboApiClient.fromConfiguredSession();
    return new WeiboService(client);
  }

  public getClient(): WeiboApiClient {
    return this.client;
  }

  public async postWeibo(input: PostWeiboInput): Promise<PostWeiboResult> {
    const text = normalizeRequiredText(input.text, "微博正文");
    const response = await this.client.requestJson<WeiboApiEnvelope<{ status?: RawMblog; id?: string | number; bid?: string }>>(
      "/api/statuses/update",
      {
        method: "POST",
        headers: {
          "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
          "x-requested-with": "XMLHttpRequest",
          origin: "https://m.weibo.cn",
          referer: "https://m.weibo.cn/compose/"
        },
        body: new URLSearchParams({ content: text })
      }
    );

    assertApiSuccess(response, "发微博");

    const status = response.data?.status;
    const fallbackId = stringifyId(response.data?.id);
    const item = status ? normalizeMblog(status) : undefined;
    const id = item?.id ?? fallbackId;

    if (!id) {
      throw new Error("发微博接口返回成功，但缺少微博 ID，无法确认发布结果。");
    }

    return {
      id,
      bid: item?.bid ?? normalizeOptionalString(response.data?.bid),
      createdAt: item?.createdAt,
      text: item?.text ?? text,
      url: item?.bid ? `https://m.weibo.cn/status/${item.bid}` : undefined
    };
  }

  public async listOwnWeibos(input: ListWeiboInput): Promise<ListWeiboItem[]> {
    const limit = normalizePositiveInteger(input.limit, "limit");
    const page = normalizePositiveInteger(input.page, "page");
    const uid = await this.resolveUid();
    const containerId = `107603${uid}`;
    const response = await this.client.requestJson<WeiboApiEnvelope<TimelineData>>("/api/container/getIndex", {
      method: "GET",
      query: {
        type: "uid",
        value: uid,
        containerid: containerId,
        page
      },
      headers: {
        referer: `https://m.weibo.cn/u/${uid}`
      }
    });

    if (response.ok === 0) {
      return [];
    }

    const cards = response.data?.cards ?? [];
    const items = cards
      .map((card) => normalizeMblog(card.mblog))
      .filter((item): item is ListWeiboItem => item !== undefined);

    return items.slice(0, limit);
  }

  public async getReposts(input: RepostsQueryInput): Promise<RepostItem[]> {
    const weiboId = normalizeRequiredText(input.weiboId, "微博 ID");
    const limit = normalizePositiveInteger(input.limit, "limit");
    const page = normalizePositiveInteger(input.page, "page");
    const response = await this.client.requestJson<WeiboApiEnvelope<RepostsData>>("/api/statuses/repostTimeline", {
      method: "GET",
      query: {
        id: weiboId,
        page,
        count: limit,
        page_size: limit
      },
      headers: {
        referer: `https://m.weibo.cn/status/${weiboId}`
      }
    });

    if (response.ok === 0 && isNoDataMessage(response.msg ?? response.message)) {
      return [];
    }

    assertApiSuccess(response, "查询微博转发");

    const data = response.data?.data ?? response.data?.list ?? [];
    return data.slice(0, limit).map(normalizeRepost).filter((item): item is RepostItem => item !== undefined);
  }

  private async resolveUid(): Promise<string> {
    if (this.resolvedUid) {
      return this.resolvedUid;
    }

    const sessionUid = normalizeOptionalString(this.client.getSession().uid);

    if (sessionUid) {
      this.resolvedUid = sessionUid;
      return sessionUid;
    }

    const probe = await this.client.validateSession();

    if (!probe.uid) {
      throw new Error("当前登录态缺少 uid。请在本地配置中补充 WEIBO_UID，或重新运行 login 生成带 uid 的登录态。");
    }

    this.resolvedUid = probe.uid;
    return probe.uid;
  }
}

function normalizeMblog(raw: RawMblog | undefined): ListWeiboItem | undefined {
  const id = stringifyId(raw?.id);

  if (!id) {
    return undefined;
  }

  return {
    id,
    bid: normalizeOptionalString(raw?.bid),
    createdAt: normalizeOptionalString(raw?.created_at),
    text: htmlToPlainText(raw?.text),
    source: normalizeOptionalString(raw?.source),
    repostsCount: normalizeOptionalNumber(raw?.reposts_count),
    commentsCount: normalizeOptionalNumber(raw?.comments_count),
    attitudesCount: normalizeOptionalNumber(raw?.attitudes_count)
  };
}

function normalizeRepost(raw: RawMblog | undefined): RepostItem | undefined {
  const base = normalizeMblog(raw);

  if (!base) {
    return undefined;
  }

  return {
    id: base.id,
    createdAt: base.createdAt,
    text: base.text,
    source: base.source,
    userName: normalizeOptionalString(raw?.user?.screen_name),
    userId: stringifyId(raw?.user?.id)
  };
}

function assertApiSuccess<T>(response: WeiboApiEnvelope<T>, actionName: string): void {
  if (response.ok === 1 || response.ok === undefined) {
    return;
  }

  const details = normalizeOptionalString(response.msg) ?? normalizeOptionalString(response.message) ?? "接口未返回具体原因。";
  throw new Error(`${actionName}失败：${details}`);
}

function isNoDataMessage(message: string | undefined): boolean {
  const normalized = normalizeOptionalString(message);
  return normalized !== undefined && normalized.includes("还没有人转发过");
}

function htmlToPlainText(input: string | undefined): string {
  const normalized = normalizeOptionalString(input);

  if (!normalized) {
    return "";
  }

  return normalized
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/p>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, "\"")
    .replace(/&#39;/g, "'")
    .trim();
}

function normalizeRequiredText(value: string, fieldName: string): string {
  const normalized = value.trim();

  if (!normalized) {
    throw new Error(`${fieldName}不能为空。`);
  }

  return normalized;
}

function normalizePositiveInteger(value: number, fieldName: string): number {
  if (!Number.isInteger(value) || value <= 0) {
    throw new Error(`${fieldName} 必须是大于 0 的整数。`);
  }

  return value;
}

function normalizeOptionalString(value: string | undefined): string | undefined {
  const normalized = value?.trim();
  return normalized ? normalized : undefined;
}

function stringifyId(value: string | number | undefined): string | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }

  const normalized = String(value).trim();
  return normalized ? normalized : undefined;
}

function normalizeOptionalNumber(value: number | undefined): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}
