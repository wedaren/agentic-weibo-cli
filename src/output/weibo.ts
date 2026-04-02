/** 职责：把微博服务层结果格式化为稳定、可读的终端文本。 */
import type { ListWeiboItem, PostWeiboResult, RepostItem } from "../services/weiboService.js";

export function formatPostResult(result: PostWeiboResult): string {
  const lines = ["发布成功"];
  lines.push(`微博 ID: ${result.id}`);

  if (result.bid) {
    lines.push(`微博 BID: ${result.bid}`);
  }

  if (result.createdAt) {
    lines.push(`发布时间: ${result.createdAt}`);
  }

  if (result.url) {
    lines.push(`访问链接: ${result.url}`);
  }

  lines.push("正文:");
  lines.push(result.text);

  return `${lines.join("\n")}\n`;
}

export function formatWeiboList(items: ListWeiboItem[]): string {
  if (items.length === 0) {
    return "未查询到微博记录。\n";
  }

  const lines = items.flatMap((item, index) => formatListItem(item, index + 1));
  return `${lines.join("\n")}\n`;
}

export function formatReposts(items: RepostItem[]): string {
  if (items.length === 0) {
    return "该微博当前没有可返回的转发记录。\n";
  }

  const lines = items.flatMap((item, index) => formatRepostItem(item, index + 1));
  return `${lines.join("\n")}\n`;
}

function formatListItem(item: ListWeiboItem, index: number): string[] {
  const lines = [`[${index}] ${item.id}`];

  if (item.createdAt) {
    lines.push(`时间: ${item.createdAt}`);
  }

  if (item.source) {
    lines.push(`来源: ${item.source}`);
  }

  lines.push(
    `互动: 转发 ${item.repostsCount ?? 0} | 评论 ${item.commentsCount ?? 0} | 点赞 ${item.attitudesCount ?? 0}`
  );
  lines.push(item.text || "(空正文)");

  return lines;
}

function formatRepostItem(item: RepostItem, index: number): string[] {
  const lines = [`[${index}] ${item.id}`];

  if (item.userName || item.userId) {
    lines.push(`用户: ${item.userName ?? "未知用户"}${item.userId ? ` (${item.userId})` : ""}`);
  }

  if (item.createdAt) {
    lines.push(`时间: ${item.createdAt}`);
  }

  if (item.source) {
    lines.push(`来源: ${item.source}`);
  }

  lines.push(item.text || "(空正文)");

  return lines;
}
