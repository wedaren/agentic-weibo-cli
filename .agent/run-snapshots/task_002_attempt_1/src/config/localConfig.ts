/** Responsibility: define local config paths and environment-first config contract. */
import path from "node:path";

export interface LocalConfig {
  cookie?: string;
  uid?: string;
  defaultLimit?: number;
}

export const LOCAL_DATA_DIR = path.resolve(process.cwd(), ".local");
export const LOCAL_CONFIG_PATH = path.join(LOCAL_DATA_DIR, "weibo-session.json");
