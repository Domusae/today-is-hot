"""이미 보낸 알림을 기억해 중복 발송을 막는다.

30분마다 폴링하므로 같은 특보를 계속 다시 보내지 않도록 키를 파일에 남긴다.
GitHub Actions에서는 이 파일을 레포에 커밋해 실행 간 상태를 유지한다.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

STATE_PATH = Path(__file__).resolve().parent.parent / "state" / "sent.json"
RETENTION_DAYS = 7


def load(path: Path = STATE_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}  # 상태가 깨졌다면 빈 상태로 시작한다(최악의 경우 중복 1회).


def save(sent: dict[str, str], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sent, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def prune(sent: dict[str, str], now: datetime | None = None) -> dict[str, str]:
    """오래된 키를 지워 상태 파일이 무한정 커지지 않게 한다."""
    cutoff = (now or datetime.now()) - timedelta(days=RETENTION_DAYS)
    kept = {}
    for key, stamp in sent.items():
        try:
            if datetime.fromisoformat(stamp) >= cutoff:
                kept[key] = stamp
        except ValueError:
            continue
    return kept


def filter_new(events, sent: dict[str, str]) -> list:
    """아직 보내지 않은 이벤트만 남긴다."""
    return [e for e in events if e.key not in sent]


def mark(events, sent: dict[str, str], now: datetime | None = None) -> dict[str, str]:
    stamp = (now or datetime.now()).isoformat(timespec="seconds")
    return {**sent, **{e.key: stamp for e in events}}
