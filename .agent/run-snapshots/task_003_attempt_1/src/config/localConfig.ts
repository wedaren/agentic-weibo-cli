/** Responsibility: read and write local uncommitted config with environment-aware paths. */
import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

export interface LocalConfig {
  cookie?: string;
  uid?: string;
  defaultLimit?: number;
  loginUrl?: string;
  updatedAt?: string;
}

const DEFAULT_DATA_DIR = path.resolve(process.cwd(), ".local");

export function getLocalDataDir(): string {
  const configuredDir = process.env.WEIBO_CLI_DATA_DIR?.trim();

  return configuredDir ? path.resolve(configuredDir) : DEFAULT_DATA_DIR;
}

export function getLocalConfigPath(): string {
  return path.join(getLocalDataDir(), "weibo-session.json");
}

export async function readLocalConfig(): Promise<LocalConfig | null> {
  try {
    const raw = await readFile(getLocalConfigPath(), "utf8");
    return JSON.parse(raw) as LocalConfig;
  } catch (error) {
    if (isMissingFileError(error)) {
      return null;
    }

    throw error;
  }
}

export async function writeLocalConfig(config: LocalConfig): Promise<string> {
  const dataDir = getLocalDataDir();
  const targetPath = getLocalConfigPath();

  await mkdir(dataDir, { recursive: true });
  await writeFile(targetPath, `${JSON.stringify(config, null, 2)}\n`, {
    encoding: "utf8",
    mode: 0o600
  });

  try {
    await chmod(targetPath, 0o600);
  } catch {
    // Ignore chmod failures on platforms or filesystems that do not support POSIX permissions.
  }

  return targetPath;
}

function isMissingFileError(error: unknown): error is NodeJS.ErrnoException {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    error.code === "ENOENT"
  );
}
