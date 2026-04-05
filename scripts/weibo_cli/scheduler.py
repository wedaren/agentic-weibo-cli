"""macOS LaunchAgent-based daily sync scheduler.

仅支持 macOS。通过管理 ~/Library/LaunchAgents/com.wedaren.weibo-sync.plist
实现每日定时 sync，无需用户手动操作 launchctl 或 plist 文件。
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

LABEL = "com.wedaren.weibo-sync"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
_LOG_DIR = Path.home() / ".local" / "share" / "weibo-cli"
STDOUT_LOG = _LOG_DIR / "sync.log"
STDERR_LOG = _LOG_DIR / "sync-error.log"

_DEFAULT_HOUR = 8
_DEFAULT_MINUTE = 7
_DEFAULT_PAGES = 10


@dataclass(frozen=True, slots=True)
class ScheduleStatus:
    configured: bool        # plist 文件存在
    loaded: bool            # launchctl 已加载
    hour: int | None        # 每天触发时刻（小时）
    minute: int | None      # 每天触发时刻（分钟）
    pages: int | None       # sync 拉取页数
    plist_path: str
    log_path: str


class WeiboScheduler:
    """管理 macOS LaunchAgent 定时 sync 任务。"""

    def get_status(self) -> ScheduleStatus:
        configured = PLIST_PATH.exists()
        if not configured:
            return ScheduleStatus(
                configured=False,
                loaded=False,
                hour=None,
                minute=None,
                pages=None,
                plist_path=str(PLIST_PATH),
                log_path=str(STDOUT_LOG),
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

    def _write_plist(self, *, hour: int, minute: int, pages: int) -> None:
        skill_dir = str(Path(__file__).resolve().parents[2])
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
        <string>cd {skill_dir} &amp;&amp; scripts/weibo-cli sync --pages {pages}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{hour}</integer>
        <key>Minute</key>
        <integer>{minute}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{STDOUT_LOG}</string>
    <key>StandardErrorPath</key>
    <string>{STDERR_LOG}</string>
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
