/** Responsibility: centralize stable terminal-facing status and error messages. */
export function notImplemented(commandName: string, detail: string): never {
  throw new Error(`命令 ${commandName} 尚未实现。${detail}`);
}
