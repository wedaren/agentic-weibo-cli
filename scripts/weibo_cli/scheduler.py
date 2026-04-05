"""macOS LaunchAgent-based daily sync scheduler.

仅支持 macOS。通过管理 ~/Library/LaunchAgents/com.wedaren.weibo-sync.plist
实现每日定时 sync，无需用户手动操作 launchctl 或 plist 文件。

可观测性：
  - sync 每次执行（手动或定时）后写入 sync-status.json，记录成功/失败结果
  - sync.log 超过 MAX_LOG_BYTES 时自动轮转为 sync.log.1（保留一份）
  - `schedule logs` 可查看最近 N 行日志
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LABEL = "com.wedaren.weibo-sync"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
_LOG_DIR = Path.home() / ".local" / "share" / "weibo-cli"
STDOUT_LOG = _LOG_DIR / "sync.log"
STDERR_LOG = _LOG_DIR / "sync-error.log"
SYNC_STATUS_FILE = _LOG_DIR / "sync-status.json"
MAX_LOG_BYTES = 5 * 1024 * 1024  # 5 MB

_DEFAULT_HOUR = 8
_DEFAULT_MINUTE = 7
_DEFAULT_PAGES = 10


@dataclass(frozen=True, slots=True)
class ScheduleStatus:
    configured: bool            # plist 文件存在
    loaded: bool                # launchctl 已加载
    hour: int | None            # 每天触发时刻（小时）
    minute: int | None          # 每天触发时刻（分钟）
    pages: int | None           # sync 拉取页数
    plist_path: str
    log_path: str
    last_run_at: str | None     # 上次执行时间
    last_run_success: bool | None
    last_run_added: int | None  # 上次新增条数
    last_run_error: str | None  # 上次失败原因


def write_sync_status(*, success: bool, error: str | None = None, result: Any = None) -> None:
    """写入 sync 执行状态文件。由 cli.py 的 handle_sync() 调用。"""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    status: dict[str, Any] = {
        "last_run_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "success": success,
        "error": error,
        "added": getattr(result, "added", None),
        "skipped": getattr(result, "skipped", None),
        "purged": getattr(result, "purged", None),
        "total": getattr(result, "total", None),
        "pages_fetched": getattr(result, "pages_fetched", None),
    }
    tmp = SYNC_STATUS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.rename(SYNC_STATUS_FILE)


def rotate_log_if_needed() -> None:
    """若 sync.log 超过 MAX_LOG_BYTES，轮转为 sync.log.1（替换旧备份）。"""
    if STDOUT_LOG.exists() and STDOUT_LOG.stat().st_size > MAX_LOG_BYTES:
        rotated = STDOUT_LOG.with_suffix(".log.1")
        STDOUT_LOG.rename(rotated)


def read_last_logs(lines: int = 50) -> str:
    """读取 sync.log 最后 N 行。"""
    if not STDOUT_LOG.exists():
        return ""
    text = STDOUT_LOG.read_text(encoding="utf-8", errors="replace")
    all_lines = text.splitlines()
    return "\n".join(all_lines[-lines:])


class WeiboScheduler:
    """管理 macOS LaunchAgent 定时 sync 任务。"""

    def get_status(self) -> ScheduleStatus:
        configured = PLIST_PATH.exists()
        last_run_at, last_run_success, last_run_added, last_run_error = self._read_sync_status()
        if not configured:
            return ScheduleStatus(
                configured=False,
                loaded=False,
                hour=None,
                minute=None,
                pages=None,
                plist_path=str(PLIST_PATH),
                log_path=str(STDOUT_LOG),
                last_run_at=last_run_at,
                last_run_success=last_run_success,
                last_run_added=last_run_added,
                last_run_error=last_run_error,
            )
        hour, minute, pages = self._parse_plist()
        return ScheduleStatus(
            configured=True,
            loaded=self._is_loaded(),
            hour=hour,
            minute=minute,
            pages=pages,
            plist_path=str(PLIST_PATH),
            log_path=str(STDOUT_LOG),
            last_run_at=last_run_at,
            last_run_success=last_run_success,
            last_run_added=last_run_added,
            last_run_error=last_run_error,
        )

    def enable(
        self,
        *,
        hour: int = _DEFAULT_HOUR,
        minute: int = _DEFAULT_MINUTE,
        pages: int = _DEFAULT_PAGES,
    ) -> ScheduleStatus:
        """写入 plist 并 launchctl load。若已加载，先 unload 再重建。"""
        if self._is_loaded():
            self._unload()
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._write_plist(hour=hour, minute=minute, pages=pages)
        self._load()
        return self.get_status()

    def disable(self) -> ScheduleStatus:
        """unload 并删除 plist 文件。"""
        if self._is_loaded():
            self._unload()
        if PLIST_PATH.exists():
            PLIST_PATH.unlink()
        return self.get_status()

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _read_sync_status(self) -> tuple[str | None, bool | None, int | None, str | None]:
        if not SYNC_STATUS_FILE.exists():
            return None, None, None, None
        try:
            data = json.loads(SYNC_STATUS_FILE.read_text(encoding="utf-8"))
            return (
                data.get("last_run_at"),
                data.get("success"),
                data.get("added"),
                data.get("error"),
            )
        except Exception:  # noqa: BLE001
            return None, None, None, None

    def _write_plist(self, *, hour: int, minute: int, pages: int) -> None:
        from xml.sax.saxutils import escape as xml_escape
        skill_dir = str(Path(__file__).resolve().parents[2])
        # Shell 一行命令：先轮转日志，再执行 sync，追加输出到日志文件
        shell_cmd = (
            f"LOG={STDOUT_LOG}; "
            f"MAXSIZE={MAX_LOG_BYTES}; "
            f'[ -f "$LOG" ] && [ $(wc -c < "$LOG") -gt $MAXSIZE ] && mv "$LOG" "${{LOG}}.1"; '
            f'cd {skill_dir} && scripts/weibo-cli sync --pages {pages} >> "$LOG" 2>&1'
        )
        plist_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>-c</string>
        <string>{xml_escape(shell_cmd)}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{hour}</integer>
        <key>Minute</key>
        <integer>{minute}</integer>
    </dict>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
"""
        PLIST_PATH.write_text(plist_xml, encoding="utf-8")

    def _parse_plist(self) -> tuple[int | None, int | None, int | None]:
        try:
            text = PLIST_PATH.read_text(encoding="utf-8")
            hour_m = re.search(r"<key>Hour</key>\s*<integer>(\d+)</integer>", text)
            minute_m = re.search(r"<key>Minute</key>\s*<integer>(\d+)</integer>", text)
            pages_m = re.search(r"sync --pages (\d+)", text)
            return (
                int(hour_m.group(1)) if hour_m else None,
                int(minute_m.group(1)) if minute_m else None,
                int(pages_m.group(1)) if pages_m else None,
            )
        except Exception:  # noqa: BLE001
            return None, None, None

    def _is_loaded(self) -> bool:
        try:
            result = subprocess.run(
                ["launchctl", "list", LABEL],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:  # noqa: BLE001
            return False

    def _load(self) -> None:
        subprocess.run(
            ["launchctl", "load", str(PLIST_PATH)],
            check=True, capture_output=True, timeout=10,
        )

    def _unload(self) -> None:
        subprocess.run(
            ["launchctl", "unload", str(PLIST_PATH)],
            capture_output=True, timeout=10,
        )
